from __future__ import annotations

from enum import StrEnum, auto
from functools import cached_property
from typing import ClassVar, Self

from cached_classproperty import cached_classproperty
from pydantic import Field, InstanceOf, model_validator
from pydantic.json_schema import SkipJsonSchema

from pydantic_ai import RunContext
from pydantic_ai.messages import SystemPromptPart
from pydantic_ai.toolsets import FunctionToolset

from corio import Path, dm, strings
from corio.function import ccp, cp
from corio.iterator import ilist
from corio.strings import get_docstring
from xah.class_collections import classes
from xah.options.path import PathCwd
from xah.toolsets.base.projection import Projection
from xah.toolsets.fs.permissions import Permissions


class Kinds(StrEnum):
    READ = auto()
    EDIT = auto()
    DELETE = auto()
    MOVE = auto()
    SEARCH = auto()
    EXECUTE = auto()
    THINK = auto()
    FETCH = auto()
    SWITCH_MODE = auto()
    OTHER = auto()


class Signature(dm.Base):
    pass


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
    EXTERNALIZE_OUTPUT: ClassVar[bool] = True
    KIND: ClassVar[Kinds] = Kinds.OTHER

    ctx: SkipJsonSchema[InstanceOf[RunContext]] = Field(exclude=True)
    toolset: SkipJsonSchema[InstanceOf[FunctionToolset]] = Field(exclude=True)
    validation: SkipJsonSchema[InstanceOf[Validation]] = Field(
        default_factory=Validation,
        exclude=True,
    )

    @ccp
    def State(cls) -> type[ToolState]:
        return ToolState

    @ccp
    def sig(cls) -> type[Signature] | None:
        for base in cls.__mro__:
            if base is Signature or issubclass(base, Tool):
                continue
            if issubclass(base, Signature):
                return base
        return None

    @ccp
    def projections(cls) -> list[type[Projection]]:
        return [Projection]

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

    @cached_classproperty
    def suffix(cls) -> str:
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

    @model_validator(mode="after")
    def resolve_paths(self):
        for name, field in type(self).model_fields.items():
            for metadata in field.metadata:
                if not isinstance(metadata, Permissions):
                    continue
                value = self.resolve(getattr(self, name), metadata)
                setattr(self, name, value)
                break
        return self

    def resolve(
        self,
        path: Path | list[Path] | None,
        metadata: Permissions,
    ) -> Path | list[Path]:
        if type(path) is list:
            return [self.resolve(item, metadata) for item in path]

        cwd = self.ctx.deps.options.cls[PathCwd].value
        path = path or cwd
        path = (Path(cwd) / Path(path)).resolve()
        allowed = self.ctx.deps.options.cls[metadata.permission].value
        if not path.is_relative_to(allowed):
            permission = metadata.permission.__name__
            msg = f'Path "{path}" requires {permission} permission, but is outside "{allowed}".'
            raise ValueError(msg)

        return path

    @cached_property
    def name(self) -> str:
        return self.toolset.get_name(type(self))

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
