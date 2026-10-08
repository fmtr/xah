from xah.toolsets.terminal.base import TerminalTool


class Kill(TerminalTool):
    """Kill a background terminal process."""

    async def run(self) -> str:
        status = await self.terminal.kill()
        return f"Terminal `{self.terminal.id}` has status `{status}`."
