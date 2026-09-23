from __future__ import annotations

from collections.abc import Iterable
from difflib import SequenceMatcher
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
from xah.toolsets.base.validator import Validator


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
    def VALIDATORS(cls) -> ilist[type[Validator]]:
        return ilist()

    @classmethod
    def merge_validators(
        cls,
        inherited: Iterable[type[Validator]],
        *overrides: type[Validator],
    ) -> ilist[type[Validator]]:
        validators = {
            validator.local_name: validator
            for validator in (*inherited, *overrides)
        }
        return ilist(validators.values())

    @staticmethod
    def get_sim(old: str, new: str) -> int | None:
        similarity = round(SequenceMatcher(None, old, new).ratio() * 100)
        return similarity if similarity >= 80 else None

    @cached_property
    def name(self) -> str:
        return self.toolset.tool_name(type(self))

    @cached_property
    def policy(self):
        from xah.options.base import Policy

        return self.toolset.options.cls[Policy]

    async def validate(self) -> list[str]:
        messages = []
        for validator_class in self.VALIDATORS:
            validator = validator_class.model_validate(self, from_attributes=True)
            if validator.enabled:
                messages.extend(await validator.validate())
        return messages
