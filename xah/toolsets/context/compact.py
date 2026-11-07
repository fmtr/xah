from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.tool import Input as InputBase, Kinds, Tool


class Input(InputBase):
    def get_projection(self, request):
        title = "Compact conversation"
        if self.focus:
            title = f"Compact conversation around {self.preview(self.focus, limit=80)}"
        return AcpToolProjection(title=title)

    focus: str | None = Field(default=None, description="Optional topic to prioritize in the summary.")


class Compact(Tool, Input):
    """Request conversation compaction before the next model request."""

    KIND = Kinds.THINK

    async def run(self) -> str:
        self.ctx.deps.context_manager.request_compact(focus=self.focus)
        message = "Conversation compaction requested."
        if self.focus:
            message += f" Focus: {self.focus}."
        return f"{message} It will be applied before the next model request."
