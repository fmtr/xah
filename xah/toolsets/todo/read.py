from xah.toolsets.base.tool import Tool


class Read(Tool):
    """Read the current todo list and task IDs."""

    async def run(self) -> str:
        return self.toolset.text
