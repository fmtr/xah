from typing import ClassVar

from pydantic_ai import ModelRetry

from xah.toolsets.fs.read import Line
from xah.toolsets.terminal.base import TerminalManagementTool


class Output(TerminalManagementTool):
    """Return output produced since the previous call."""

    EVENT = "produced output"
    MAX_LINE_LENGTH: ClassVar[int] = 20_000
    MAX_OUTPUT_LENGTH: ClassVar[int] = 50_000

    @classmethod
    def format_output(cls, output: str) -> str:
        lines = [
            Line(raw=raw, num=number, max=cls.MAX_LINE_LENGTH)
            for number, raw in enumerate(output.splitlines(), 1)
        ]
        rendered = "\n".join(line.text for line in lines)
        if output.endswith(("\n", "\r")):
            rendered += "\n"

        return rendered[-cls.MAX_OUTPUT_LENGTH:]

    async def run(self) -> str:
        output = await self.terminal.get()
        if not output:
            from xah.toolsets.utils.toolset import Utils
            from xah.toolsets.utils.sleep import Sleep

            self.feedback(f"Use the {Utils.tool_name(Sleep)} tool if you need to wait for output.")
            raise ModelRetry("No output since last call.")

        return self.format_output(output)
