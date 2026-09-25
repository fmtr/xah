from functools import cached_property
from typing import Annotated, ClassVar

from cached_classproperty import cached_classproperty
from pydantic import Field
from pydantic_ai import ModelRetry

from corio import Path, strings
from xah.constants import PROJECTION_EDIT_TOOL_NAMES
from xah.toolsets.fs.permissions import FileTool, Permissions, PermissionsValidator
from xah.toolsets.fs.similarity import get_similarity


class Edit(FileTool):
    """Edit a file by exact string replacement."""

    path: Annotated[Path, Permissions(Permissions.Read, Permissions.Write)] = Field(
        description="File path relative to the working directory.",
    )
    old_text: str = Field(description="Exact text to replace.")
    new_text: str = Field(description="Replacement text.")
    replace_all: bool = Field(default=False, description="Replace every exact occurrence.")

    projections: ClassVar = PROJECTION_EDIT_TOOL_NAMES

    @cached_classproperty
    def VALIDATORS(cls):
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
    @cached_property
    def enabled(self) -> bool:
        return True

    async def validate(self) -> list[str]:
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

        return []


class EditWarnings(Edit):
    MIN_LENGTH: ClassVar[int] = 250
    MIN_SIMILARITY: ClassVar[int] = 80

    async def validate(self) -> list[str]:
        messages = []
        if min(len(self.old_text), len(self.new_text)) < self.MIN_LENGTH:
            return messages

        similarity = get_similarity(self.old_text, self.new_text)
        if similarity < self.MIN_SIMILARITY:
            return messages
        message = f"Your old and new strings are {similarity}% similar. Replace only the smallest substring that changes."
        messages.append(message)
        return messages
