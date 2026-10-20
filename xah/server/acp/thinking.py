from __future__ import annotations

from typing import Any

from acp import update_agent_thought_text
from acp.schema import (
    AgentMessageChunk,
    AgentThoughtChunk,
    TextContentBlock,
    ToolCallStart,
    UsageUpdate,
)
from pydantic_acp.runtime.adapter import PydanticAcpAgent
from pydantic_acp.runtime._prompt_execution import _PromptExecution
from pydantic_acp.runtime.prompts import PromptBlock, PromptRunOutcome
from pydantic_acp.session.state import AcpSessionContext
from pydantic_ai import Agent, AgentRunResultEvent, UsageLimits
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    RetryPromptPart,
    ThinkingPart,
    ThinkingPartDelta,
)

from xah.server.acp.usage import UsageReporterRegistry
from xah.obs import logger

from pydantic_acp.projection import (
    _is_output_tool,
    build_tool_progress_update,
    build_tool_start_update,
)


class ThinkingPromptExecution(_PromptExecution):
    """Forward Pydantic AI thinking events as native ACP thought chunks."""

    async def run_prompt(
        self,
        *,
        agent: Agent[Any, Any],
        prompt: list[PromptBlock],
        session: AcpSessionContext,
        output_type_override: object | None = None,
    ) -> PromptRunOutcome:
        try:
            return await super().run_prompt(
                agent=agent,
                prompt=prompt,
                session=session,
                output_type_override=output_type_override,
            )
        except Exception:
            logger.error("ACP prompt execution failed", _exc_info=True)
            raise

    async def _record_execution_updates(self, **kwargs):
        await super()._record_execution_updates(**kwargs)
        reporter = self._runtime._owner.usage_reporters.for_session(
            kwargs["session"].session_id
        )
        if reporter.used is None:
            return
        update = UsageUpdate(
            session_update="usage_update",
            used=reporter.used,
            size=reporter.size,
        )
        await self._runtime._owner._client.session_update(
            session_id=kwargs["session"].session_id,
            update=update,
        )

    @staticmethod
    def thought_update_from_event(event: Any):
        if isinstance(event, PartStartEvent) and isinstance(event.part, ThinkingPart):
            return update_agent_thought_text(event.part.content)
        if isinstance(event, PartDeltaEvent) and isinstance(event.delta, ThinkingPartDelta):
            if event.delta.content_delta:
                return update_agent_thought_text(event.delta.content_delta)
        return None

    async def _consume_run_events(
        self,
        stream: Any,
        *,
        known_starts: dict[str, ToolCallStart],
        message_id: str,
        projection_map: Any,
        session: Any,
        streamed_output: bool,
    ):
        async for event in stream:
            if isinstance(event, AgentRunResultEvent):
                return event.result, streamed_output
            if self._runtime._owner._config.enable_generic_tool_projection and isinstance(
                event,
                FunctionToolCallEvent,
            ):
                if _is_output_tool(event.part.tool_name) or event.part.tool_call_id in known_starts:
                    continue
                start_update = build_tool_start_update(
                    event.part,
                    classifier=self._runtime._owner._tool_classifier,
                    cwd=session.cwd,
                    projection_map=projection_map,
                )
                known_starts[event.part.tool_call_id] = start_update
                await self._runtime._record_update(session, start_update)
                continue
            if self._runtime._owner._config.enable_generic_tool_projection and isinstance(
                event,
                FunctionToolResultEvent,
            ):
                result_part = event.part
                if isinstance(result_part, RetryPromptPart):
                    if result_part.tool_name is None or _is_output_tool(result_part.tool_name):
                        continue
                elif _is_output_tool(result_part.tool_name):
                    continue
                await self._runtime._record_update(
                    session,
                    build_tool_progress_update(
                        result_part,
                        classifier=self._runtime._owner._tool_classifier,
                        cwd=session.cwd,
                        known_start=known_starts.get(result_part.tool_call_id),
                        projection_map=projection_map,
                        serializer=self._runtime._owner._config.output_serializer,
                    ),
                )
                continue

            thought_update = self.thought_update_from_event(event)
            if thought_update is not None:
                streamed_output = True
                await self._runtime._owner._record_update(session, thought_update)
                continue

            text_chunk = self._runtime._text_chunk_from_event(event)
            if text_chunk is None or text_chunk == "":
                continue
            streamed_output = True
            await self._runtime._record_update(
                session,
                AgentMessageChunk(
                    session_update="agent_message_chunk",
                    content=TextContentBlock(type="text", text=text_chunk),
                    message_id=message_id,
                ),
            )

        raise RuntimeError("missing_agent_run_result")


class AgentAcp(PydanticAcpAgent):
    """ACP agent that forwards Pydantic AI thinking events."""

    def __init__(self, *args, usage_reporters: UsageReporterRegistry, **kwargs):
        super().__init__(*args, **kwargs)
        self.usage_reporters = usage_reporters
        self._prompt_runtime._execution = ThinkingPromptExecution(self._prompt_runtime)

    def __call__(self, conn):
        del conn
        return type(self)(
            self._agent_source,
            config=self._connection_factory_config,
            usage_reporters=self.usage_reporters,
        )

    async def initialize(
        self,
        protocol_version,
        client_capabilities=None,
        client_info=None,
        **kwargs,
    ):
        response = await super().initialize(
            protocol_version,
            client_capabilities=client_capabilities,
            client_info=client_info,
            **kwargs,
        )
        self._agent_source.client_info = client_info
        return response

    def _build_run_kwargs(self, **kwargs):
        run_kwargs = super()._build_run_kwargs(**kwargs)
        run_kwargs["usage_limits"] = UsageLimits(request_limit=None)
        reporter = self.usage_reporters.for_session(kwargs["session"].session_id)
        reporter.begin(kwargs["model_override"])
        return run_kwargs

    async def _record_update(self, session, update):
        """Send thought chunks without storing them in pydantic-acp's transcript.

        pydantic-acp 1.5.1's stored transcript union does not include
        ``AgentThoughtChunk``, although ACP supports it as a live session
        update.  Persisting one through the base implementation raises before
        the update reaches the client.
        """
        if isinstance(update, AgentThoughtChunk):
            if self._client is not None:
                await self._client.session_update(
                    session_id=session.session_id,
                    update=update,
                )
            return
        await super()._record_update(session, update)

    def _restore_default_model(self, agent, session):
        del agent, session
        return False
