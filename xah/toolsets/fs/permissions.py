from typing import ClassVar

from pydantic import model_validator
from pydantic_ai import ModelRetry

from corio import Path
from xah.options.path import PathRead, PathWrite, SelectPath
from xah.toolsets.base.tool import Tool, ValidationResult


class Permissions(frozenset[type[SelectPath]]):
    Read: ClassVar[type[SelectPath]] = PathRead
    Write: ClassVar[type[SelectPath]] = PathWrite

    def __new__(cls, *permissions: type[SelectPath]):
        return super().__new__(cls, permissions)


class FileTool(Tool):
    @model_validator(mode="after")
    def resolve_paths(self):
        for name, field in type(self).model_fields.items():
            if any(isinstance(metadata, Permissions) for metadata in field.metadata):
                value = getattr(self, name)
                setattr(self, name, (self.ctx.deps.cwd / value).resolve())
        return self


class PermissionsValidator:
    def validate_path(self, path: Path, permission: type[SelectPath]) -> None:
        allowed = self.ctx.deps.options.cls[permission].value
        if not path.is_relative_to(allowed):
            raise ModelRetry(f'Permission Denied: "{path}" is outside "{allowed}".')

    async def validate(self, result: ValidationResult):
        for name, field in type(self).model_fields.items():
            permissions = next(
                (metadata for metadata in field.metadata if isinstance(metadata, Permissions)),
                (),
            )
            for permission in permissions:
                self.validate_path(getattr(self, name), permission)
