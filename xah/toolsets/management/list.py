from corio import strings
from corio.function import ccp
from xah.toolsets.base.tool import Tool, ToolState
from xah.toolsets.base.toolset import ToolsetInfo


class List(Tool):
    """List available toolsets and their activation state."""

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
