from functools import cached_property
from typing import Annotated, ClassVar

from cached_classproperty import cached_classproperty
from xah.class_collections import classes
from pydantic import Field
from pydantic_ai import ModelRetry

from corio import Path, strings
from xah.constants import PROJECTION_EDIT_TOOL_NAMES
from xah.toolsets.fs.permissions import FileTool, Permissions, PermissionsValidator
from xah.toolsets.fs.similarity import SimilarityValidator


class Edit(FileTool):
    """Edit a file by exact string replacement."""

    path: Annotated[Path, Permissions(Permissions.Read, Permissions.Write)] = Field(
        description="File path relative to the working directory.",
    )
    old_text: str = Field(description="Exact text to replace.")
    new_text: str = Field(description="Replacement text.")
    replace_all: bool = Field(default=False, description="Replace every exact occurrence.")

    PROJECTIONS: ClassVar[str] = PROJECTION_EDIT_TOOL_NAMES

    @classes
    def Validators(cls):
        return [EditPermissions, ValidEdit, EditWarnings]

    @cached_property
    def current(self) -> str:
        return self.path.read_text(errors="replace")

    @cached_property
    def updated(self) -> str:
        count = -1 if self.replace_all else 1
        return self.current.replace(self.old_text, self.new_text, count)

    async def run(self) -> str:
        occurrences = self.current.count(self.old_text)
        self.path.write_text(self.updated)
        count = occurrences if self.replace_all else 1
        return f"Edited {self.path}: replaced {strings.suffix_plural(count, 'occurrence')}"


class EditPermissions(PermissionsValidator, Edit):
    pass


class ValidEdit(Edit):
    async def validate(self):
        if not self.path.is_file():
            raise ModelRetry(f'Path "{self.path}" does not exist.')
        if not self.old_text:
            raise ModelRetry("Old text must not be empty.")

        occurrences = self.current.count(self.old_text)
        if not occurrences:
            raise ModelRetry(f"String {self.old_text!r} not found in file")

        if occurrences > 1 and not self.replace_all:
            occurrence_count = strings.suffix_plural(occurrences, "time")
            raise ModelRetry(
                f"String found {occurrence_count}. Use replace_all or provide more context.",
            )



class EditWarnings(SimilarityValidator, Edit):
    async def validate(self):
        self.validation.messages.extend(self.similarity_warnings(
            self.old_text,
            self.new_text,
            "Your old and new strings are {similarity}% similar. Replace only the smallest substring that changes.",
        ))
