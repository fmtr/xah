from __future__ import annotations

from functools import cached_property
from typing import ClassVar

from cached_classproperty import cached_classproperty
from pydantic import Field, InstanceOf
from pydantic.json_schema import SkipJsonSchema
from pydantic_acp import ProjectionMap
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from corio import dm
from corio.iterator import ilist
from corio.strings import get_docstring
from xah.class_collections import ClassDeclaration, resolve_class_collection


class Tool(dm.Base):
    ctx: SkipJsonSchema[InstanceOf[RunContext]] = Field(exclude=True)
    toolset: SkipJsonSchema[InstanceOf[FunctionToolset]] = Field(exclude=True)

    NAME: ClassVar[str | None] = None
    DESCRIPTION: ClassVar[str | None] = None
    projections: ClassVar[
        str | ProjectionMap | list[str | ProjectionMap] | None
    ] = None

    @cached_classproperty
    def local_name(cls) -> str:
        return cls.NAME or cls.__name__

    @cached_classproperty
    def description(cls) -> str | None:
        if cls.DESCRIPTION:
            return cls.DESCRIPTION

        for base in cls.__mro__:
            if description := get_docstring(base):
                return description
        return None

    @cached_classproperty
    def VALIDATORS(cls) -> ClassDeclaration[Tool]:
        return []

    @cached_property
    def validator_classes(self) -> ilist[type[Tool]]:
        return resolve_class_collection(type(self), "VALIDATORS", "local_name")

    @cached_property
    def name(self) -> str:
        return self.toolset.tool_name(type(self))

    @cached_property
    def policy(self):
        from xah.options.base import Policy

        return self.toolset.options.cls[Policy]

    @cached_property
    def enabled(self) -> bool:
        return self.policy.approval

    async def validate(self) -> list[str]:
        messages = []
        for validator_class in self.validator_classes:
            validator = validator_class.model_validate(self, from_attributes=True)
            if validator.enabled:
                messages.extend(await validator.validate())
        return messages
