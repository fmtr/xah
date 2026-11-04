from corio import strings
from corio.function import ccp
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.projection import Projection as ProjectionBase
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase, Tool, ToolState
from xah.toolsets.base.toolset import ToolsetInfo


class Projection(ProjectionBase):
    def start(self):
        return AcpToolProjection(title="List toolsets")


class Signature(SignatureBase):
    """No arguments are required to list toolsets."""


class List(Tool, Signature):
    """List available toolsets and their activation state."""

    KIND = Kinds.READ

    @ccp
    def Projection(cls):
        return Projection

    @ccp
    def State(cls) -> type[ToolState]:
        class State(ToolState):
            called: bool = False

            def after_compress(self):
                self.called = False

        return State

    async def run(self) -> list[ToolsetInfo]:
        if self.state.called:
            self.feedback(strings.trim("""
                You have already listed the toolsets. These will not change during a given session.
            """))
        else:
            self.state.called = True

        return [toolset.info for toolset in self.ctx.deps.toolsets.permitted]
