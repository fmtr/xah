from xah.toolsets.base.tool import Tool
from xah.toolsets.base.toolset import ToolsetInfo


class List(Tool):
    """List available toolsets and their activation state."""

    async def run(self) -> list[ToolsetInfo]:
        return [toolset.info for toolset in self.ctx.deps.toolsets.permitted]
