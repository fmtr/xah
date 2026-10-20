from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Any, ClassVar, Generic, TypeVar

from cached_classproperty import cached_classproperty
from pydantic import ValidationError, ConfigDict
from pydantic_ai import ModelRetry, RunContext, Tool as PydanticTool, ToolFailed
from pydantic_ai.messages import InstructionPart, SystemPromptPart
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import FunctionToolset, ToolsetTool

from corio import strings
from corio.function import ccm, cp
from corio.iterator import ilist
from corio.strings import get_docstring
from xah.class_collections import classes
from xah.constants import HARNESS_FEEDBACK
from xah.obs import logger
from xah.options import base as options
from xah.toolsets.base.approval import ApprovalRequiredToolsetMetadata
from xah.toolsets.base.tool import Tool, ToolState, Validation


AgentDepsT = TypeVar("AgentDepsT", contravariant=True)


@dataclass
class ToolsetInfo:
    active: bool
    name: str
    desc: str | None
    protected: bool
    tools: list[str]


class Toolset(FunctionToolset[AgentDepsT], Generic[AgentDepsT]):

    model_config = ConfigDict(ignored_types=(cached_classproperty,))

    DESCRIPTION: ClassVar[str | None] = None
    IS_MANAGEMENT: ClassVar[bool] = False
    POLICY: ClassVar[str] = options.Policy.Policies.FULL

    @cached_classproperty
    def name(cls) -> str:
        return cls.__name__

    @cached_classproperty
    def description(cls) -> str | None:
        if cls.DESCRIPTION:
            return cls.DESCRIPTION

        for base in cls.__mro__:
            if description := get_docstring(base):
                return description
            if base is Toolset:
                return None

    @cp
    def info(self) -> ToolsetInfo:
        return ToolsetInfo(
            active=self.activated,
            name=self.name,
            desc=self.description,
            protected=self.options.cls[options.Policy].value == options.Policy.Policies.REQUESTABLE,
            tools=[Tool.local_name for Tool in self.Tools]
        )

    async def get_instructions(self, ctx: RunContext[AgentDepsT]) -> list[InstructionPart] | None:
        del ctx
        return None

    @classes
    def Tools(cls) -> list[type[Tool]]:
        return []

    @cp
    def states(self) -> dict[tuple[type[Tool], type[Tool]], ToolState]:
        state_classes = []
        for tool_class in self.Tools:
            state_classes.append(((tool_class, tool_class), tool_class))
            state_classes.extend(
                ((tool_class, validator_class), validator_class)
                for validator_class in tool_class.Validators
            )

        return {
            state_key: state_class.State()
            for state_key, state_class in state_classes
        }

    def state_for(
        self,
        owner_class: type[Tool],
        state_class: type[Tool],
    ) -> ToolState:
        return self.states[(owner_class, state_class)]

    @cached_classproperty
    def projections(cls) -> list:
        projections = []
        for tool_class in cls.Tools:
            tool_name = cls.tool_name(tool_class)
            projection=tool_class.build_projections(tool_name)
            projections.extend(projection)
        return projections

    def __init__(self, activated: bool = True, **kwargs):
        del kwargs
        self.activated = activated
        super().__init__(id=self.name)
        for tool_class in self.Tools:
            self.register(tool_class)

    @ccm
    def tool_name(cls, tool_class: type[Tool]) -> str:
        return f"{cls.name}-{tool_class.local_name}"

    @ccm
    def local_tool_name(cls, name: str) -> str:
        return name.removeprefix(f"{cls.name}-")

    @staticmethod
    def feedback(ctx: RunContext, message: str | SystemPromptPart) -> str | None:
        if isinstance(message, str):
            message = strings.trim(HARNESS_FEEDBACK, message)
            message = SystemPromptPart(content=message)

        return ctx.enqueue(message)

    async def raise_errors(self, method, *args):
        try:
            return await method(*args)
        except (ModelRetry, ToolFailed):
            raise
        except Exception as exception:
            logger.error(str(exception), _exc_info=True)
            raise ToolFailed("Internal error")

    def register(self, tool_class: type[Tool]) -> None:
        """Register the framework-facing constructor for a tool class."""
        async def get_instance(
            ctx: RunContext[AgentDepsT],
            **tool_args: Any,
        ) -> Tool:
            return self.instances.id[ctx.tool_call_id]

        pydantic_tool = PydanticTool.from_schema(
            function=get_instance,
            name=self.tool_name(tool_class),
            description=tool_class.description,
            json_schema=tool_class.model_json_schema(),
            takes_ctx=True,
        )
        self.add_tool(pydantic_tool)

    def after_compress(self):
        for state in self.states.values():
            state.after_compress()

    @cached_property
    def options(self) -> ilist[options.Select]:
        return ilist([
            options.Policy.from_value(
                name=self.name,
                value=self.POLICY,
                description=self.description,
            )
        ])

    @cached_property
    def wrapper(self) -> ApprovalRequiredToolsetMetadata[AgentDepsT]:
        return ApprovalRequiredToolsetMetadata(self, self.validate)

    @cached_property
    def instances(self) -> ilist[Tool]:
        return ilist()

    @staticmethod
    def validation_error_message(error: ValidationError) -> str:
        details = error.errors(
            include_context=False,
            include_input=False,
            include_url=False,
        )
        messages = []
        for detail in details:
            location = ".".join(str(part) for part in detail["loc"])
            description = detail["msg"]
            message = f"{location}: {description}"
            messages.append(message)

        return strings.trim(*messages)

    def init_tool(
        self,
        ctx: RunContext[AgentDepsT],
        tool_def: ToolDefinition,
        tool_args: dict[str, Any],
    ) -> Tool:
        local_name = self.local_tool_name(tool_def.name)
        tool_class = self.Tools.local_name[local_name]
        try:
            instance = tool_class(
                ctx=ctx,
                toolset=self,
                state=self.state_for(tool_class, tool_class),
                **tool_args,
            )
        except ValidationError as error:
            raise ModelRetry(self.validation_error_message(error)) from error
        return instance

    async def validate(
        self,
        ctx: RunContext[AgentDepsT],
        tool_def: ToolDefinition,
        tool_args: dict[str, Any],
    ) -> Validation:
        instance = self.init_tool(ctx, tool_def, tool_args)
        self.instances.append(instance)
        keep_instance = False
        try:
            await self.raise_errors(instance.validate)
            if instance.validation.messages.errors:
                raise ModelRetry(instance.validation.messages.errors.text)
            keep_instance = True
            return instance.validation
        finally:
            if not keep_instance:
                self.instances.remove(instance)

    async def after_approval(self, instance: Tool):
        await self.raise_errors(instance.after_approval)
        for validator in instance.validators:
            await self.raise_errors(validator.after_approval)

    async def after_decline(self, tool_call_id: str):
        instance = self.instances.id[tool_call_id]
        try:
            await self.raise_errors(instance.after_decline)
            for validator in instance.validators:
                await self.raise_errors(validator.after_decline)
        finally:
            self.instances.remove(self.instances.id[tool_call_id])

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[AgentDepsT],
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        """Execute the retained tool instance after validation and approval."""
        if ctx.tool_call_id not in self.instances.id:
            await self.validate(ctx, tool.tool_def, tool_args)
        instance = self.instances.id[ctx.tool_call_id]
        try:
            instance = await super().call_tool(name, tool_args, ctx, tool)
            if ctx.tool_call_approved:
                await self.after_approval(instance)

            run_result = await self.raise_errors(instance.run)
        finally:
            self.instances.remove(self.instances.id[ctx.tool_call_id])

        if instance.validation.messages.warnings:
            instance.feedback(
                strings.trim(
                    f"The {name} tool completed, but issued the following warnings. Avoid these issues in subsequent calls.",
                    instance.validation.messages.warnings.text,
                )
            )

        return run_result
