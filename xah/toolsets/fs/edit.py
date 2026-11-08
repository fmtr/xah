from functools import cached_property
from typing import Annotated

from xah.class_collections import classes
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from corio import Path, strings
from acp.schema import FileEditToolCallContent
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.output import OutputString
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.fs.permissions import Permissions
from xah.toolsets.fs.similarity import SimilarityValidator

class FileEditOutput(OutputString):
    location_line: SkipJsonSchema[int | None] = Field(default=None, exclude=True)

    @property
    def projection(self):
        request = self.request
        input = request.input
        location = self.tool_location(input.path, line=self.location_line)
        path = location.path
        return AcpToolProjection(
            content=[
                FileEditToolCallContent(type="diff", path=path, old_text=input.old_text, new_text=input.new_text),
                #self.content_block(self.output)


            ],
            locations=[location],
            title=self.title,
            status=request.status,
        )


class Input(InputBase):
    path: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="File path relative to the working directory.",
    )
    old_text: str = Field(description="Exact text to replace.")
    new_text: str = Field(description="Replacement text.")
    replace_all: bool = Field(default=False, description="Replace every exact occurrence.")

    @property
    def title(self):
        return f"Editing `{self.path.name}`"

    @property
    def projection(self):
        request = self.request
        location = self.tool_location(self.path)
        return AcpToolProjection(
            content=[FileEditToolCallContent(type="diff", path=location.path, old_text=self.old_text, new_text=self.new_text)],
            locations=[location],
            title=self.title,
        )

class Edit(Tool, Input):
    """Edit a file by exact string replacement."""

    KIND = Kinds.EDIT

    @classes
    def Validators(cls):
        return [ValidEdit, EditWarnings]

    @cached_property
    def current(self) -> str:
        return self.path.read_text(errors="replace")

    @cached_property
    def updated(self) -> str:
        count = -1 if self.replace_all else 1
        return self.current.replace(self.old_text, self.new_text, count)

    async def run(self) -> FileEditOutput:
        occurrences = self.current.count(self.old_text)
        location_line = self.current[:self.current.index(self.old_text)].count("\n")
        self.path.write_text(self.updated)
        count = occurrences if self.replace_all else 1
        return FileEditOutput(
            output=f"Edited {self.path}: replaced {strings.suffix_plural(count, 'occurrence')}",
            location_line=location_line,
        )


class ValidEdit(Edit):
    async def validate(self):
        if not self.path.is_file():
            self.validation.messages.errors.append(f'Path "{self.path}" does not exist.')
            self.validation.abort = True
            return
        if not self.old_text:
            self.validation.messages.errors.append("Old text must not be empty.")
            self.validation.abort = True
            return

        occurrences = self.current.count(self.old_text)
        if not occurrences:
            self.validation.messages.errors.append(f"String {self.old_text!r} not found in file")
            self.validation.abort = True
            return

        if occurrences > 1 and not self.replace_all:
            occurrence_count = strings.suffix_plural(occurrences, "time")
            self.validation.messages.errors.append(
                f"String found {occurrence_count}. Use replace_all or provide more context."
            )
            self.validation.abort = True



class EditWarnings(SimilarityValidator, Edit):
    async def validate(self):
        messages = self.similarity_warnings(
            self.old_text,
            self.new_text,
            "Your old and new strings are {similarity}% similar. Replace only the smallest substring that changes.",
        )
        self.messages.extend(messages)
