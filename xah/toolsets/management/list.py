from corio import strings
from corio.function import ccp
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.output import Output
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool, ToolState
from xah.toolsets.base.toolset import ToolsetInfo


class Input(InputBase):
    """No arguments are required to list toolsets."""

    @property
    def projection(self):
        request = self.request
        return AcpToolProjection(title="List toolsets")


class ListOutput(Output):
    toolsets: list[ToolsetInfo]

    @property
    def agent(self):
        return self.toolsets


class List(Tool, Input):
    """List available toolsets and their activation state."""

    KIND = Kinds.READ

    @ccp
    def State(cls) -> type[ToolState]:
        class State(ToolState):
            called: bool = False

            def after_compress(self):
                self.called = False

        return State

    async def run(self) -> ListOutput:
        if self.state.called:
            self.feedback(strings.trim("""
                You have already listed the toolsets. These will not change during a given session.
            """))
        else:
            self.state.called = True

        return ListOutput(toolsets=[toolset.info for toolset in self.ctx.deps.toolsets.permitted])
