from typing import Annotated

from pydantic import Field

from corio import Path, strings
from xah.class_collections import classes
from acp.schema import FileEditToolCallContent
from xah.toolsets.base.output import Output
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.fs.permissions import Permissions
from xah.toolsets.fs.similarity import SimilarityValidator


class FileWriteOutput(Output):
    path: Path
    text: str

    @property
    def agent(self) -> str:
        line_count = len(self.text.splitlines())
        return f"Wrote {line_count} lines to {self.path}"

    @property
    def content(self):
        return [
            FileEditToolCallContent(
                type="diff",
                path=self.locations[0].path,
                old_text="",
                new_text=self.text,
            ),
        ]

    @property
    def locations(self):
        return [self.tool_location(self.path)]


class Input(InputBase):
    path: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="Destination path relative to the working directory.",
    )
    text: str = Field(description="Text to write to the file.")

    @property
    def title(self):
        line_count = strings.suffix_plural(len(self.text.splitlines()), "line")
        return f"Writing {line_count} to `{self.path.name}`"

    @property
    def content(self):
        location = self.tool_location(self.path)
        return [FileEditToolCallContent(type="diff", path=location.path, old_text="", new_text=self.text)]

    @property
    def locations(self):
        return [self.tool_location(self.path)]

class Write(Tool, Input):
    """Write text to a file."""

    KIND = Kinds.MOVE

    @classes
    def Validators(cls):
        return [WriteWarnings]

    async def run(self) -> FileWriteOutput:
        self.path.parent.mkdirf()
        self.path.write_text(self.text)
        return FileWriteOutput(path=self.path, text=self.text)


class WriteWarnings(SimilarityValidator, Write):
    async def validate(self):
        if not self.path.is_file():
            return

        current = self.path.read_text(errors="replace")
        messages = self.similarity_warnings(
            current,
            self.text,
            "You are overwriting a file with {similarity}% similar content. Use partial reads and edits for small changes.",
        )
        self.messages.extend(messages)
