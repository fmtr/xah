from functools import cached_property
from typing import Annotated

from xah.class_collections import classes
from pydantic import Field

from corio import Path, strings
from acp.schema import FileEditToolCallContent
from xah.toolsets.base.output import Output
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.fs.permissions import Permissions
from xah.toolsets.fs.similarity import SimilarityValidator


class FileEditOutput(Output):
    path: Path
    old_text: str
    new_text: str
    occurrence_count: int
    location_line: int

    @property
    def agent(self) -> str:
        count = strings.suffix_plural(self.occurrence_count, "occurrence")
        return f"Edited {self.path}: replaced {count}"

    @property
    def content(self):
        return [
            FileEditToolCallContent(
                type="diff",
                path=self.locations[0].path,
                old_text=self.old_text,
                new_text=self.new_text,
            ),
        ]

    @property
    def locations(self):
        return [self.tool_location(self.path, line=self.location_line)]


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
    def content(self):
        location = self.tool_location(self.path)
        return [FileEditToolCallContent(type="diff", path=location.path, old_text=self.old_text, new_text=self.new_text)]

    @property
    def locations(self):
        return [self.tool_location(self.path)]

class Edit(Tool, Input):
    """Edit a file by exact string replacement."""

    KIND = Kinds.MOVE

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
            path=self.path,
            old_text=self.old_text,
            new_text=self.new_text,
            occurrence_count=count,
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
