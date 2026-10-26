from xah.toolsets.terminal.base import TerminalManagementTool


class Status(TerminalManagementTool):
    """Return the current status of a background terminal."""

    EVENT = "finished"

    async def run(self) -> str:
        return self.message
