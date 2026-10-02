from pydantic import Field

from xah.toolsets.base.tool import Tool


class Compact(Tool):
    """Request conversation compaction before the next model request."""

    focus: str | None = Field(
        default=None,
        description="Optional topic to prioritize in the summary.",
    )

    async def run(self) -> str:
        self.ctx.deps.context_manager.request_compact(focus=self.focus)
        message = "Conversation compaction requested."
        if self.focus:
            message += f" Focus: {self.focus}."
        return f"{message} It will be applied before the next model request."
