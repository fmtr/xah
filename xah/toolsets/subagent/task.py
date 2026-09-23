from typing import Any

from pydantic import Field
from pydantic_deep import DEFAULT_USAGE_LIMITS
from subagents_pydantic_ai.prompts import get_task_instructions_prompt
from subagents_pydantic_ai.retry import run_with_retry
from subagents_pydantic_ai.toolset import _serialize_output

from xah.options import base as options
from xah.toolsets.base.tool import Tool


class Task(Tool):
    """Delegate a bounded task to a context-free subagent and return its result."""

    prompt: str = Field(
        description="Self-contained task prompt with paths, context, behavior, and validation requirements.",
    )

    def get_subagent_deps(self):
        from xah.toolsets.subagent.toolset import Subagent

        deps = self.ctx.deps.clone_for_subagent()
        deps.toolsets.cls[Subagent].options.cls[options.Policy].current_value = options.DISABLED
        return deps

    def get_subagent_toolsets(self) -> list[Any]:
        if self.ctx.deps.ask_user is None:
            return []
        return [self.toolset.ask_parent_toolset]

    async def run(self) -> str:
        run_kwargs = {
            "deps": self.get_subagent_deps(),
            "toolsets": self.get_subagent_toolsets(),
            "usage_limits": DEFAULT_USAGE_LIMITS,
        }
        result = await run_with_retry(
            self.ctx.deps.subagents["default"],
            get_task_instructions_prompt(self.prompt, can_ask_questions=True, max_questions=None),
            run_kwargs=run_kwargs,
            retry=self.toolset.retry,
        )
        return _serialize_output(result.output)
