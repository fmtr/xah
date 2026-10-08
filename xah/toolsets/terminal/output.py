from typing import ClassVar

from pydantic_ai import RunContext, ToolFailed

from corio import strings
from xah.toolsets.base.toolset import Toolset
from xah.toolsets.terminal.base import TerminalTool
from xah.toolsets.terminal.terminal import Terminal


class Output(TerminalTool):
    """Return output produced since the previous call."""

    LAST_OUTPUT_CHARS: ClassVar[int] = 512

    async def run(self) -> str:
        output = await self.terminal.get()
        if not output:
            raise ToolFailed("No output since last call.")
        return output

    @classmethod
    def notify(cls, ctx: RunContext, terminal: Terminal) -> None:
        output_tail = terminal.output[-cls.LAST_OUTPUT_CHARS:]
        message = strings.trim(f"""
        Terminal `{terminal.id}` produced output.
        This is only the last {cls.LAST_OUTPUT_CHARS} characters of the output:

        ```
        {output_tail}
        ```

        Use Terminals-Output with terminal_id `{terminal.id}` to inspect the whole output.
        """)
        Toolset.feedback(ctx, message)
