from xah.toolsets.terminal.base import TerminalTool


class Status(TerminalTool):
    """Return the current status of a background terminal."""

    EVENT = "finished"

    async def run(self) -> str:
        terminal = self.terminal
        return f"Terminal `{terminal.id}` is {terminal.status}."
