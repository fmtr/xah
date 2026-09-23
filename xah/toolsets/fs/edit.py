from functools import cached_property
from typing import Annotated, ClassVar

from pydantic import Field
from pydantic_ai import ModelRetry

from corio import Path, strings
from xah.constants import PROJECTION_EDIT_TOOL_NAMES
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.validator import Validator
from xah.toolsets.fs.sig import FileSig, PATH_READ, PATH_WRITE, Permissions, PermissionsValidator


class EditSig(FileSig):
    path: Annotated[Path, Permissions(PATH_READ, PATH_WRITE)] = Field(
        description="File path relative to the working directory.",
    )
    old_text: str = Field(description="Exact text to replace.")
    new_text: str = Field(description="Replacement text.")
    replace_all: bool = Field(default=False, description="Replace every exact occurrence.")

    @cached_property
    def current(self) -> str:
        return self.path.read_text(errors="replace")

    @cached_property
    def updated(self) -> str:
        if self.replace_all:
            count = -1
        else:
            count = 1

        return self.current.replace(self.old_text, self.new_text, count)


class EditPermissions(PermissionsValidator, EditSig):
    pass


class ValidEdit(Validator, EditSig):
    @cached_property
    def enabled(self) -> bool:
        return True

    async def validate(self) -> list[str]:
        if not self.path.is_file():
            raise ModelRetry(f'Path "{self.path}" does not exist.')

        occurrences = self.current.count(self.old_text)

        if not occurrences:
            raise ModelRetry(f"String {self.old_text!r} not found in file")

        if occurrences > 1 and not self.replace_all:
            occurrence_count = strings.suffix_plural(occurrences, "time")
            raise ModelRetry(
                f"String found {occurrence_count}. Use replace_all or provide more context.",
            )

        return []


class EditWarnings(Validator, EditSig):
    async def validate(self) -> list[str]:
        messages = []

        if similarity := self.get_sim(self.old_text, self.new_text):
            message = f"Your old and new strings are {similarity}% similar. Replace only the smallest substring that changes."
            messages.append(
                message,
            )

        return messages


class Edit(Tool, EditSig):
    """Edit a file by exact string replacement."""

    VALIDATORS: ClassVar = (EditPermissions, ValidEdit, EditWarnings)
    projections: ClassVar = PROJECTION_EDIT_TOOL_NAMES

    async def run(self) -> str:
        occurrences = self.current.count(self.old_text)
        self.path.write_text(self.updated)

        if self.replace_all:
            count = occurrences
        else:
            count = 1

        return f"Edited {self.path}: replaced {strings.suffix_plural(count, 'occurrence')}"
