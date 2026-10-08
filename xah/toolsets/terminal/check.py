from pydantic_ai import RunContext

from corio import strings
from xah.toolsets.base.toolset import Toolset
from xah.toolsets.terminal.base import TerminalTool
from xah.toolsets.terminal.terminal import Terminal


class Check(TerminalTool):
    """Return the current status of a background terminal."""

    async def run(self) -> str:
        terminal = self.terminal
        return f"Terminal `{terminal.id}` is {terminal.status}."

    @classmethod
    def notify(cls, ctx: RunContext, terminal: Terminal) -> None:
        message = strings.trim(f"""
        Terminal `{terminal.id}` finished with status `{terminal.status}`.
        Use Terminals-Output with terminal_id `{terminal.id}` to inspect its output.
        """)
        Toolset.feedback(ctx, message)
