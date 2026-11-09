from typing import Annotated, ClassVar

from pydantic import Field
from pydantic_ai import ModelRetry

from corio import Path, strings
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.class_collections import classes
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.output import Output
from xah.toolsets.base.tool import Kinds
from xah.toolsets.fs.file import FileTool
from xah.toolsets.fs.permissions import Permissions


class ReadLineOutput(Output):
    line_number: int
    text: str

    @property
    def agent(self) -> str:
        return f"{self.line_number}:{self.text}"

    @property
    def content(self):
        return [self.content_block(self.agent)]

    @property
    def locations(self):
        return [
            self.tool_location(
                self.request.input.path,
                line=self.line_number - 1,
            ),
        ]


class Input(InputBase):
    path: Annotated[Path, Permissions(Permissions.Read)] = Field(
        description="File path relative to the working directory.",
    )
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

    @property
    def title(self):
        return f"Reading line {self.line_number} from `{self.path.name}`"

    @property
    def projection(self):
        return AcpToolProjection(
            title=self.title,
            locations=[self.tool_location(self.path, line=self.line_number - 1)],
        )


class ReadLine(FileTool, Input):
    """

    Read a bounded character range from a single line in a file.

    Only to be used in niche cases where a single, very long line contains important content, but truncated by other tools.

    """

    KIND = Kinds.READ

    EXTERNALIZE_OUTPUT: ClassVar[bool] = False

    async def run(self) -> ReadLineOutput:
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
                        Use regular tools like {Files.get_name(Read)} instead.
                    """)
                    raise ModelRetry(msg)


                result = text[self.offset:self.offset + self.limit]
                remaining = len(text) - self.offset - len(result)
                if remaining > 0:
                    self.feedback(f"The line contains {remaining} characters beyond the displayed range.")
                return ReadLineOutput(line_number=number, text=result)

        raise ModelRetry(f"Line {self.line_number} does not exist in '{self.path}', which contains {number} lines.")
