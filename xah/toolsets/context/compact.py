from pydantic import Field
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool


class Input(InputBase):
    @property
    def title(self):
        if self.focus:
            return f"Compacting conversation around `{self.preview(self.focus, limit=20)}`"
        return "Compacting conversation"


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
