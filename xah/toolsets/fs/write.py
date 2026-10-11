from typing import Annotated, ClassVar

from cached_classproperty import cached_classproperty
from xah.class_collections import classes
from pydantic import Field

from corio import Path
from xah.constants import PROJECTION_WRITE_TOOL_NAMES
from xah.toolsets.fs.permissions import FileTool, Permissions, PermissionsValidator
from xah.toolsets.fs.similarity import SimilarityValidator


class Write(FileTool):
    """Write complete content to a file."""

    path: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="Destination path relative to the working directory.",
    )
    content: str = Field(description="Complete file content to write.")

    PROJECTIONS: ClassVar[str] = PROJECTION_WRITE_TOOL_NAMES

    @classes
    def Validators(cls):
        return [WritePermissions, WriteWarnings]

    async def run(self) -> str:
        self.path.parent.mkdirf()
        self.path.write_text(self.content)
        return f"Wrote {len(self.content.splitlines())} lines to {self.path}"


class WritePermissions(PermissionsValidator, Write):
    pass


class WriteWarnings(SimilarityValidator, Write):
    async def validate(self):
        if not self.path.is_file():
            return

        current = self.path.read_text(errors="replace")
        self.validation.messages.extend(self.similarity_warnings(
            current,
            self.content,
            "You are overwriting a file with {similarity}% similar content. Use partial reads and edits for small changes.",
        ))
