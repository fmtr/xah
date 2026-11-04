from typing import Annotated, ClassVar

from pydantic import Field
from pydantic_ai import ModelRetry

from corio import Path, strings
from corio.function import ccp
from xah.class_collections import classes
from xah.toolsets.fs.read import Projection as ReadProjection
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase
from xah.toolsets.fs.file import FileTool
from xah.toolsets.fs.permissions import Permissions



class Projection(ReadProjection):
    pass


class Signature(SignatureBase):
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


class ReadLine(FileTool, Signature):
    """

    Read a bounded character range from a single line in a file.

    Only to be used in niche cases where a single, very long line contains important content, but truncated by other tools.

    """

    KIND = Kinds.READ

    @ccp
    def Projection(cls):
        return Projection

    EXTERNALIZE_OUTPUT: ClassVar[bool] = False

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
                        Use regular tools like {Files.get_name(Read)} instead.
                    """)
                    raise ModelRetry(msg)


                result = text[self.offset:self.offset + self.limit]
                remaining = len(text) - self.offset - len(result)
                output = f"{number}:{result}"
                if remaining > 0:
                    self.feedback(f"The line contains {remaining} characters beyond the displayed range.")
                return output

        raise ModelRetry(f"Line {self.line_number} does not exist in '{self.path}', which contains {number} lines.")
