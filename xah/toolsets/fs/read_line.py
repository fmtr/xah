from typing import ClassVar

from pydantic import Field
from pydantic_ai import ModelRetry

from corio import strings
from xah.constants import PROJECTION_READ_TOOL_NAMES
from xah.toolsets.fs.file import FileTool



class ReadLine(FileTool):
    """

    Read a bounded character range from a single line in a file.

    Only to be used in niche cases where a single, very long line contains important content, but truncated by other tools.

    """

    line_number: int = Field(
        ge=1,
        description="One-based line number to read.",
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Zero-based character offset within the line.",
    )
    limit: int = Field(
        default=20_000,
        gt=0,
        le=20_000,
        description="Maximum number of characters to return.",
    )

    EXTERNALIZE_OUTPUT: ClassVar[bool] = False
    PROJECTIONS: ClassVar[str] = PROJECTION_READ_TOOL_NAMES

    async def run(self) -> str:
        number=0
        with self.path.open(errors="replace") as file:
            for number, raw_line in enumerate(file, 1):
                if number != self.line_number:
                    continue

                text = raw_line.rstrip("\r\n")

                from xah.toolsets.fs.read import Read
                if len(text) < Read.MAX_LINE_LENGTH /2:
                    from xah.toolsets.fs.toolset import Files
                    msg=strings.trim(f"""
                        The selected line is {len(text)} chars long. 
                        This tool is for reading extremely long lines.
                        Use regular tools like {Files.tool_name(Read)} instead.
                    """)
                    raise ModelRetry(msg)


                result = text[self.offset:self.offset + self.limit]
                remaining = len(text) - self.offset - len(result)
                output = f"{number}:{result}"
                if remaining > 0:
                    self.feedback(f"The line contains {remaining} characters beyond the displayed range.")
                return output

        raise ModelRetry(f"Line {self.line_number} does not exist in '{self.path}', which contains {number} lines.")
