from functools import cached_property
from typing import Annotated

from xah.class_collections import classes
from pydantic import Field

from corio import Path, strings
from acp.schema import FileEditToolCallContent, ToolCallLocation
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.output import OutputString, ProjectionRequest
from xah.toolsets.base.tool import Input as InputBase, Kinds, Tool
from xah.toolsets.fs.permissions import Permissions
from xah.toolsets.fs.similarity import SimilarityValidator


class FileEditOutput(OutputString):
    def get_projection(self, request: ProjectionRequest):
        input = request.input
        path = str(input.path)
        return AcpToolProjection(
            content=[FileEditToolCallContent(type="diff", path=path, old_text=input.old_text, new_text=input.new_text)],
            locations=[ToolCallLocation(path=path)],
            title=request.tool_name,
            status=request.status,
        )


class Input(InputBase):
    path: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="File path relative to the working directory.",
    )
    old_text: str = Field(description="Exact text to replace.")
    new_text: str = Field(description="Replacement text.")
    replace_all: bool = Field(default=False, description="Replace every exact occurrence.")

    def get_projection(self, request):
        path = str(self.path)
        return AcpToolProjection(
            content=[FileEditToolCallContent(type="diff", path=path, old_text=self.old_text, new_text=self.new_text)],
            locations=[ToolCallLocation(path=path)],
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
        self.path.write_text(self.updated)
        count = occurrences if self.replace_all else 1
        return FileEditOutput(
            output=f"Edited {self.path}: replaced {strings.suffix_plural(count, 'occurrence')}"
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
