from xah.toolsets.base.tool import Tool
from xah.toolsets.todo.sig import TodoSig


class Read(Tool, TodoSig):
    """Read the current todo list and task IDs."""
    async def run(self) -> str:
        return self.toolset.text
