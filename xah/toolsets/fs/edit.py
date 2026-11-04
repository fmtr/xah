from functools import cached_property
from typing import Annotated

from xah.class_collections import classes
from pydantic import Field

from corio import Path, strings
from corio.function import ccp, cp
from xah.toolsets.base.projection import FileEditProjection
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase, Tool
from xah.toolsets.fs.permissions import Permissions
from xah.toolsets.fs.similarity import SimilarityValidator


class Projection(FileEditProjection):
    @cp
    def old_text(self) -> str:
        return self.sig.old_text

    @cp
    def new_text(self) -> str:
        return self.sig.new_text


class Signature(SignatureBase):
    path: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="File path relative to the working directory.",
    )
    old_text: str = Field(description="Exact text to replace.")
    new_text: str = Field(description="Replacement text.")
    replace_all: bool = Field(default=False, description="Replace every exact occurrence.")


class Edit(Tool, Signature):
    """Edit a file by exact string replacement."""

    KIND = Kinds.EDIT

    @ccp
    def Projection(cls):
        return Projection

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

    async def run(self) -> str:
        occurrences = self.current.count(self.old_text)
        self.path.write_text(self.updated)
        count = occurrences if self.replace_all else 1
        return f"Edited {self.path}: replaced {strings.suffix_plural(count, 'occurrence')}"


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
