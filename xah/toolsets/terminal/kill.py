from xah.toolsets.terminal.base import TerminalManagementTool


class Kill(TerminalManagementTool):
    """Kill a background terminal process."""

    async def run(self) -> str:
        status = await self.terminal.kill()
        return f"Terminal `{self.terminal.id}` has status `{status}`."
