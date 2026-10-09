from xah.toolsets.terminal.base import TerminalManagementTool


class Status(TerminalManagementTool):
    """Return the current status of a background terminal."""

    EVENT = "finished"

    async def run(self) -> str:
        terminal = self.terminal
        return f"Terminal `{terminal.id}` is {terminal.status}."
