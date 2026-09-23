from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING, Annotated

from cached_classproperty import cached_classproperty
from pydantic import Field, InstanceOf
from pydantic.json_schema import SkipJsonSchema
from pydantic_ai import RunContext

from corio import dm

if TYPE_CHECKING:
    from xah.toolsets.base.toolset import Base as ToolsetBase


class Sig(dm.Base):
    ctx: Annotated[
        SkipJsonSchema[InstanceOf[RunContext]],
        Field(exclude=True),
    ]

    @cached_classproperty
    def toolset_type(cls) -> type[ToolsetBase]:
        raise NotImplementedError

    @cached_property
    def toolset(self) -> ToolsetBase:
        return self.ctx.deps.toolsets.cls[self.toolset_type]

    @cached_property
    def policy(self):
        from xah.options.base import Policy

        return self.toolset.options.cls[Policy]
