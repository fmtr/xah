from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar, Protocol

from cached_classproperty import cached_classproperty
from pydantic_acp import ProjectionMap

from corio.strings import get_docstring
from xah.toolsets.base.validator import Validator

if TYPE_CHECKING:
    from xah.toolsets.base.toolset import Base as ToolsetBase


class Tool:
    NAME: ClassVar[str | None] = None
    DESCRIPTION: ClassVar[str | None] = None
    VALIDATORS: ClassVar[tuple[type[Validator], ...]] = ()
    projections: ClassVar[
        str | ProjectionMap | list[str | ProjectionMap] | None
    ] = None

    @cached_classproperty
    def name(cls) -> str:
        local_name = cls.NAME or cls.__name__
        return f"{cls.toolset_type.name}-{local_name}"

    @cached_classproperty
    def description(cls) -> str | None:
        if cls.DESCRIPTION:
            return cls.DESCRIPTION

        for base in cls.__mro__:
            if description := get_docstring(base):
                return description
        return None

    async def validate(self) -> list[str]:
        messages = []
        for validator_class in self.VALIDATORS:
            validator = validator_class.model_validate(self, from_attributes=True)
            if validator.enabled:
                messages.extend(await validator.validate())
        return messages


class ToolModel(Protocol):
    name: ClassVar[str]
    description: ClassVar[str | None]

    def __init__(self, **data: Any) -> None: ...

    @classmethod
    def model_json_schema(cls) -> dict[str, Any]: ...

    async def validate(self) -> list[str]: ...

    async def run(self) -> Any: ...
