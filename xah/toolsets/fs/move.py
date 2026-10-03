from typing import Annotated, ClassVar

from cached_classproperty import cached_classproperty
from pydantic import Field
from pydantic_ai import ModelRetry

from corio import Path
from xah.constants import PROJECTION_WRITE_TOOL_NAMES
from xah.toolsets.fs.permissions import FileTool, Permissions, PermissionsValidator
from xah.toolsets.base.tool import ValidationResult


class Move(FileTool):
    """Move or copy a file or directory."""

    source: Annotated[Path, Permissions(Permissions.Read)] = Field(
        description="Existing file or directory to move or copy.",
    )
    target: Annotated[Path, Permissions(Permissions.Write)] = Field(description="Destination path.")
    is_copy: bool = Field(default=False, description="Copy the source instead of moving it.")

    PROJECTIONS: ClassVar[str] = PROJECTION_WRITE_TOOL_NAMES

    @cached_classproperty
    def VALIDATORS(cls):
        return [MovePermissions]

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


class MovePermissions(PermissionsValidator, Move):
    async def validate(self, result: ValidationResult):
        await super().validate(result)
        if not self.is_copy:
            self.validate_path(self.source, Permissions.Write)
