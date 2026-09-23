from typing import Annotated, ClassVar

from pydantic import Field
from pydantic_ai import ModelRetry

from corio import Path
from xah.constants import PROJECTION_WRITE_TOOL_NAMES
from xah.toolsets.base.tool import Tool
from xah.toolsets.fs.sig import FileSig, PATH_READ, PATH_WRITE, Permissions, PermissionsValidator


class MoveSig(FileSig):
    source: Annotated[Path, Permissions(PATH_READ)] = Field(
        description="Existing file or directory to move or copy.",
    )
    target: Annotated[Path, Permissions(PATH_WRITE)] = Field(description="Destination path.")
    is_copy: bool = Field(default=False, description="Copy the source instead of moving it.")


class MovePermissions(PermissionsValidator, MoveSig):
    async def validate(self) -> list[str]:
        await super().validate()

        if not self.is_copy:
            self.validate_path(self.source, PATH_WRITE)

        return []


class Move(Tool, MoveSig):
    """Move or copy a file or directory."""

    projections: ClassVar = PROJECTION_WRITE_TOOL_NAMES
    VALIDATORS: ClassVar = (MovePermissions,)

    async def run(self) -> str:
        if self.is_copy:
            operation = self.source.copy
            action = "Copied"
        else:
            operation = self.source.move
            action = "Moved"

        try:
            operation(self.target)
        except OSError as error:
            raise ModelRetry(str(error)) from error

        return f"{action} '{self.source}' to '{self.target}'."
