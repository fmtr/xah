from typing import ClassVar

from pydantic import model_validator
from pydantic_ai import ModelRetry

from corio import Path
from xah.options.path import PathRead, PathWrite
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.validator import Validator


PATH_READ = "read"
PATH_WRITE = "write"


class Permissions(frozenset[str]):
    def __new__(cls, *permissions: str):
        return super().__new__(cls, permissions)


class FileTool(Tool):
    @model_validator(mode="after")
    def resolve_paths(self):
        for name, field in type(self).model_fields.items():
            if any(isinstance(metadata, Permissions) for metadata in field.metadata):
                value = getattr(self, name)
                setattr(self, name, (self.ctx.deps.cwd / value).resolve())
        return self


class PermissionsValidator(Validator):
    OPTION_TYPES: ClassVar = {
        PATH_READ: PathRead,
        PATH_WRITE: PathWrite,
    }

    def validate_path(self, path: Path, permission: str) -> None:
        allowed = self.ctx.deps.options.cls[self.OPTION_TYPES[permission]].value
        if not path.is_relative_to(allowed):
            raise ModelRetry(f'Permission Denied: "{path}" is outside "{allowed}".')

    async def validate(self) -> list[str]:
        for name, field in type(self).model_fields.items():
            permissions = next(
                (metadata for metadata in field.metadata if isinstance(metadata, Permissions)),
                (),
            )
            for permission in permissions:
                self.validate_path(getattr(self, name), permission)
        return []
