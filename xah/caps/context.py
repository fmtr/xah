from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    SystemPromptPart,
    UserPromptPart,
)
from pydantic_ai_summarization import DEFAULT_CONTINUATION_PROMPT, async_count_tokens
from pydantic_deep import ContextManagerCapability

from xah.toolsets.context.compact import Compact
from xah.toolsets.context.toolset import Context


@dataclass
class AgentSummaryContextManager(ContextManagerCapability):
    _requested_summary: str | None = field(default=None, init=False, repr=False)
    _resolved_model_id: str | None = field(default=None, init=False, repr=False)

    def request_compact_with_summary(self, summary: str) -> None:
        self._requested_summary = summary
        self.request_compact()

    async def for_run(self, ctx: RunContext) -> "AgentSummaryContextManager":
        model_id = ctx.model.model_id
        if self.max_tokens is None and model_id != self._resolved_model_id:
            self._resolved_max_tokens = 200_000
            self._resolved_model_id = model_id

        await super().for_run(ctx)
        return self

    async def before_model_request(self, ctx: RunContext, request_context: Any) -> Any:
        messages: list[ModelMessage] = request_context.messages
        max_tokens = self._resolved_max_tokens
        total = await async_count_tokens(self.token_counter, messages)
        usage = total / max_tokens

        if self.on_usage_update is not None:
            self.on_usage_update(usage, total, max_tokens)

        if self._requested_summary is None:
            threshold = ctx.deps.models.current.CONTEXT_COMPACTION_THRESHOLD
            if usage >= threshold:
                context_toolset = ctx.deps.toolsets.all.cls[Context]
                message = Context.COMPACTION_REQUIRED_MESSAGE.format(
                    usage=usage,
                    toolset_name=Context.name,
                    tool_name=Context.get_name(Compact),
                )
                context_toolset.feedback(ctx, message)

        force = self._compact_requested
        self._compact_requested = False
        focus = self._compact_focus
        self._compact_focus = None
        messages = await self._run_compression(messages, focus, force=force)

        if messages is not request_context.messages:
            new_total = await async_count_tokens(self.token_counter, messages)
            new_usage = new_total / max_tokens
            if self.on_usage_update is not None:
                self.on_usage_update(new_usage, new_total, max_tokens)

        request_context.messages = messages
        return request_context

    async def _run_compression(
        self,
        messages: list[ModelMessage],
        focus: str | None,
        *,
        force: bool,
    ) -> list[ModelMessage]:
        summary = self._requested_summary
        if summary is None:
            return messages

        self._requested_summary = None
        assert self._summarization_processor is not None
        plan = await self._summarization_processor.plan_compression(messages, force=force)
        if plan is None:
            return messages

        if self.on_before_compress is not None:
            self.on_before_compress(messages, plan.cutoff_index)

        summary_part = UserPromptPart(content=f"{DEFAULT_CONTINUATION_PROMPT}{summary}")
        summary_message = ModelRequest(parts=[*plan.system_parts, summary_part])
        messages = [summary_message, *plan.preserved_messages]
        self._compression_count += 1

        if self.on_after_compress is None:
            return messages

        reinject = self.on_after_compress(messages, True, summary)
        if not isinstance(reinject, str) or not messages:
            return messages

        first = messages[0]
        if not isinstance(first, ModelRequest):
            return messages

        messages[0] = ModelRequest(
            parts=[*first.parts, SystemPromptPart(content=reinject)],
            instructions=first.instructions,
        )
        return messages
