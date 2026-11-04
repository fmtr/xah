from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from corio.function import ccp
from xah.toolsets.base.projection import Projection as ProjectionBase
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase, Tool


class Projection(ProjectionBase):
    def start(self):
        title = "Compact conversation"
        if self.sig.focus:
            title = f"Compact conversation around {self.preview(self.sig.focus, limit=80)}"
        return AcpToolProjection(title=title)


class Signature(SignatureBase):
    focus: str | None = Field(default=None, description="Optional topic to prioritize in the summary.")


class Compact(Tool, Signature):
    """Request conversation compaction before the next model request."""

    KIND = Kinds.THINK

    @ccp
    def Projection(cls):
        return Projection

    async def run(self) -> str:
        self.ctx.deps.context_manager.request_compact(focus=self.focus)
        message = "Conversation compaction requested."
        if self.focus:
            message += f" Focus: {self.focus}."
        return f"{message} It will be applied before the next model request."
