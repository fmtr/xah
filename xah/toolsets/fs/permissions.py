from typing import ClassVar

from pydantic import model_validator

from corio import Path
from corio.iterator import enlist
from xah.options.path import PathRead, PathWrite, SelectPath
from xah.toolsets.base.tool import Tool


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
                values = enlist(value)
                resolved = [(self.cwd / item).resolve() for item in values]
                value = resolved[0] if isinstance(value, Path) else resolved
                setattr(self, name, value)
        return self


class PermissionsValidator:
    def validate_path(self, path: Path, permission: type[SelectPath]) -> None:
        allowed = self.ctx.deps.options.cls[permission].value
        if not path.is_relative_to(allowed):
            self.validation.messages.errors.append(
                f'Permission Denied: "{path}" is outside "{allowed}".'
            )
            self.validation.abort = True

    async def validate(self):
        for name, field in type(self).model_fields.items():
            permissions = next(
                (metadata for metadata in field.metadata if isinstance(metadata, Permissions)),
                (),
            )
            if not permissions:
                continue

            paths = enlist(getattr(self, name))
            for path in paths:
                for permission in permissions:
                    self.validate_path(path, permission)
                    if self.validation.abort:
                        return

                if path.stem == ".env":
                    self.validation.approval = True
                    self.validation.messages.approval.append(f'Accessing secrets file: "{path}"')
