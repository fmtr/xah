from pydantic_ai import ToolFailed
from pydantic_ai import ToolFailed

from xah.toolsets.terminal.base import TerminalTool


class Output(TerminalTool):
    """Return output produced since the previous call."""

    EVENT = "produced output"

    async def run(self) -> str:
        output = await self.terminal.get()
        if not output:
            raise ToolFailed("No output since last call.")
        return output
