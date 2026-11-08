from typing import Annotated

from xah.class_collections import classes
from pydantic import Field

from corio import Path, strings
from xah.class_collections import classes
from acp.schema import FileEditToolCallContent
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.output import OutputString
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.fs.permissions import Permissions
from xah.toolsets.fs.similarity import SimilarityValidator


class FileWriteOutput(OutputString):
    @property
    def projection(self):
        request = self.request
        input = request.input
        location = self.tool_location(input.path)
        path = location.path
        return AcpToolProjection(
            content=[FileEditToolCallContent(type="diff", path=path, old_text="", new_text=input.content)],
            locations=[location],
            title=self.title,
            status=request.status,
        )


class Input(InputBase):
    path: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="Destination path relative to the working directory.",
    )
    content: str = Field(description="Complete file content to write.")

    @property
    def title(self):
        line_count = strings.suffix_plural(len(self.content.splitlines()), "line")
        return f"Writing {line_count} to `{self.path.name}`"

    @property
    def projection(self):
        location = self.tool_location(self.path)
        return AcpToolProjection(
            content=[FileEditToolCallContent(type="diff", path=location.path, old_text="", new_text=self.content)],
            locations=[location],
            title=self.title,
        )

class Write(Tool, Input):
    """Write complete content to a file."""

    KIND = Kinds.EDIT

    @classes
    def Validators(cls):
        return [WriteWarnings]

    async def run(self) -> FileWriteOutput:
        self.path.parent.mkdirf()
        self.path.write_text(self.content)
        return FileWriteOutput(
            output=f"Wrote {len(self.content.splitlines())} lines to {self.path}"
        )


class WriteWarnings(SimilarityValidator, Write):
    async def validate(self):
        if not self.path.is_file():
            return

        current = self.path.read_text(errors="replace")
        messages = self.similarity_warnings(
            current,
            self.content,
            "You are overwriting a file with {similarity}% similar content. Use partial reads and edits for small changes.",
        )
        self.messages.extend(messages)
