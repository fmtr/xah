from __future__ import annotations

from functools import cached_property
from typing import ClassVar, Self

from cached_classproperty import cached_classproperty
from pydantic import Field, InstanceOf
from pydantic.json_schema import SkipJsonSchema
from pydantic_acp import ProjectionMap
from pydantic_ai import RunContext
from pydantic_ai.messages import SystemPromptPart
from pydantic_ai.toolsets import FunctionToolset

from corio import Path, dm, strings
from corio.function import ccp, cp
from corio.iterator import enlist, ilist
from corio.strings import get_docstring
from xah.class_collections import classes
from xah.options.path import PathCwd


class ToolState(dm.Base):
    """Serializable state shared by instances of one tool class."""

    def after_compress(self):
        pass


class MessageList(ilist[str]):
    @property
    def text(self) -> str:
        return "\n".join(self)


class Messages(dm.Base):
    approval: MessageList = Field(default_factory=MessageList)
    decline: MessageList = Field(default_factory=MessageList)
    errors: MessageList = Field(default_factory=MessageList)
    warnings: MessageList = Field(default_factory=MessageList)


class Validation(dm.Base):
    messages: Messages = Field(default_factory=Messages)
    approval: bool = False
    abort: bool = False

    def __bool__(self) -> bool:
        return self.approval


class Tool(dm.Base):
    ctx: SkipJsonSchema[InstanceOf[RunContext]] = Field(exclude=True)
    toolset: SkipJsonSchema[InstanceOf[FunctionToolset]] = Field(exclude=True)
    validation: SkipJsonSchema[InstanceOf[Validation]] = Field(
        default_factory=Validation,
        exclude=True,
    )

    @ccp
    def State(cls) -> type[ToolState]:
        return ToolState

    state: SkipJsonSchema[InstanceOf[ToolState]] | None = Field(
        default=None,
        exclude=True,
    )

    @cp
    def call_id(self) -> str:
        return self.ctx.tool_call_id

    def model_post_init(self, __context):
        if self.state is None:
            self.state = self.State()

    NAME: ClassVar[str | None] = None
    DESCRIPTION: ClassVar[str | None] = None
    PROJECTIONS: ClassVar[str | list[str]] = []

    @classmethod
    def build_projection(cls, field_name: str, tool_name: str | None = None) -> ProjectionMap:
        from pydantic_acp import FileSystemProjectionMap, HarnessFileSystemProjectionMap
        from xah.constants import (
            PROJECTION_BASH_TOOL_NAMES,
            PROJECTION_EDIT_TOOL_NAMES,
            PROJECTION_READ_TOOL_NAMES,
            PROJECTION_SEARCH_TOOL_NAMES,
            PROJECTION_WRITE_TOOL_NAMES,
        )

        tool_name = tool_name or cls.local_name
        if field_name == PROJECTION_BASH_TOOL_NAMES:
            return FileSystemProjectionMap(
                bash_tool_names=frozenset({tool_name}), command_arg="shell"
            )

        projection_fields = {
            PROJECTION_READ_TOOL_NAMES: frozenset(),
            PROJECTION_WRITE_TOOL_NAMES: frozenset(),
            PROJECTION_EDIT_TOOL_NAMES: frozenset(),
            PROJECTION_SEARCH_TOOL_NAMES: frozenset(),
        }
        projection_fields[field_name] = frozenset({tool_name})
        return HarnessFileSystemProjectionMap(**projection_fields)

    @classmethod
    def build_projections(cls, tool_name: str) -> list[ProjectionMap]:
        projections = []
        for field_name in enlist(cls.PROJECTIONS):
            projections.append(cls.build_projection(field_name, tool_name))
        return projections

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

    @classes
    def Validators(cls) -> list[type[Tool]]:
        return []

    @cp
    def validators(self) -> ilist[Self]:
        validators = ilist()
        for validator_class in self.Validators:
            validator = validator_class.model_validate(self, from_attributes=True)
            validator.validation = self.validation
            validator.state = self.toolset.state_for(type(self), validator_class)
            validators.append(validator)
        return validators

    @cached_property
    def cwd(self) -> Path:
        return self.ctx.deps.options.cls[PathCwd].value

    @cached_property
    def name(self) -> str:
        return self.toolset.tool_name(type(self))

    @cached_property
    def policy(self):
        from xah.options.base import Policy

        return self.toolset.options.cls[Policy]

    @cached_property
    def approval(self) -> bool:
        return self.policy.approval

    @cached_property
    def is_auto(self) -> bool:
        """Return whether the toolset uses automatic approval policy."""
        from xah.options import base as options

        return self.policy.value == options.Policy.Policies.AUTO

    @property
    def messages(self) -> MessageList:
        if self.is_auto:
            return self.validation.messages.errors

        return self.validation.messages.warnings

    def feedback(self, message: str | SystemPromptPart) -> str | None:
        """Enqueue harness feedback for the next model request."""
        from xah.toolsets.base.toolset import Toolset

        feedback = message if isinstance(message, str) else message.content
        feedback = strings.trim(
            f"{self.name} ({self.ctx.tool_call_id}) reported:",
            feedback,
        )
        return Toolset.feedback(self.ctx, feedback)

    async def validate(self):
        self.validation.approval = self.approval
        for validator in self.validators:
            await validator.validate()
            if self.validation.abort:
                break

    async def after_approval(self):
        pass

    async def after_decline(self):
        pass
