from __future__ import annotations
from collections.abc import Iterator
from difflib import SequenceMatcher
from functools import cached_property
from typing import ClassVar, Literal, Self

from cached_classproperty import cached_classproperty
from pydantic import model_validator
from pydantic_ai import ModelRetry

from corio import Path
from xah.toolsets.base.sig import Sig
from xah.toolsets.base.validator import Validator

PATH_READ: Literal["PathRead"] = "PathRead"
PATH_WRITE: Literal["PathWrite"] = "PathWrite"
PermissionName = Literal["PathRead", "PathWrite"]


class Permissions(frozenset[PermissionName]):
    def __new__(cls, *permissions: PermissionName) -> Self:
        return super().__new__(cls, permissions)


class FileSig(Sig):
    SIM_LEN_THRESHOLD: ClassVar[int] = 256
    SIM_THRESHOLD: ClassVar[float] = 0.9

    @cached_classproperty
    def toolset_type(cls):
        from xah.toolsets.fs.toolset import Files
        return Files

    @classmethod
    def get_sim(cls, existing_text: str, content: str) -> float:
        if len(content) + len(existing_text) < cls.SIM_LEN_THRESHOLD:
            return 0.0

        similarity = SequenceMatcher(None, existing_text, content, autojunk=False).ratio()

        if similarity < cls.SIM_THRESHOLD:
            return 0.0

        return round(similarity * 100)

    @model_validator(mode="after")
    def resolve_paths(self) -> Self:
        for field_name, _permissions in self.path_fields():
            path = getattr(self, field_name)
            setattr(self, field_name, (self.ctx.deps.cwd / path).absolute().resolve())
        return self

    @classmethod
    def path_fields(cls) -> Iterator[tuple[str, Permissions]]:
        for field_name, field in cls.model_fields.items():
            for metadata in field.metadata:
                if isinstance(metadata, Permissions):
                    yield field_name, metadata


class PermissionsValidator(Validator):
    @cached_property
    def enabled(self) -> bool:
        return True

    def validate_path(self, path: Path, option_name: PermissionName) -> None:
        permitted = self.ctx.deps.options.name[option_name].value
        if not path.is_relative_to(permitted):
            raise ModelRetry(f'Permission Denied: Path "{path}" is outside {option_name}.')

    async def validate(self) -> list[str]:
        for field_name, permissions in self.path_fields():
            path = getattr(self, field_name)
            for permission in sorted(permissions):
                self.validate_path(path, permission)
        return []
