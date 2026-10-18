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
        """
        Register the framework-facing constructor for a tool class.

        The preflight hooks construct temporary instances directly because
        they run before Pydantic AI dispatches the registered tool. The
        registered constructor is the execution path used by ``call_tool``.
        """
        async def construct(
            ctx: RunContext[AgentDepsT],
            **tool_args: Any,
        ) -> Tool:
            try:
                return tool_class(
                    ctx=ctx,
                    toolset=self,
                    state=self.state_for(tool_class, tool_class),
                    validation=self.validations[ctx.tool_call_id],
                    **tool_args,
                )
            except ValidationError as error:
                raise ModelRetry(self.validation_error_message(error)) from error

        pydantic_tool = PydanticTool.from_schema(
            function=construct,
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
    def validations(self) -> dict[str | None, Validation]:
        return {}

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
        validation: Validation,
    ) -> Tool:
        """
        Initialize a temporary tool for preflight inspection.

        This direct constructor is separate from the registered constructor
        used by Pydantic AI during execution because approval runs before the
        framework dispatches the tool.
        """
        local_name = self.local_tool_name(tool_def.name)
        tool_class = self.Tools.local_name[local_name]
        try:
            return tool_class(
                ctx=ctx,
                toolset=self,
                state=self.state_for(tool_class, tool_class),
                validation=validation,
                **tool_args,
            )
        except ValidationError as error:
            raise ModelRetry(self.validation_error_message(error)) from error

    async def validate(
        self,
        ctx: RunContext[AgentDepsT],
        tool_def: ToolDefinition,
        tool_args: dict[str, Any],
    ) -> Validation:
        validation = Validation()
        instance = self.init_tool(ctx, tool_def, tool_args, validation)
        validation.approval = instance.approval
        validation.raise_for_messages = instance.raise_on_warn
        await self.raise_errors(instance.validate)
        self.validations[ctx.tool_call_id] = validation
        return validation

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[AgentDepsT],
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        """
        Execute a tool after its approval-bridge validation.

        The validation result is keyed by the framework tool-call ID so the
        approved retry can reuse the exact preflight result.
        """
        if ctx.tool_call_id not in self.validations:
            await self.validate(ctx, tool.tool_def, tool_args) # Validation didn't already run during approval prompt check (i.e. we're a non-ACP/subagent).
        validation = self.validations[ctx.tool_call_id]
        instance = await super().call_tool(name, tool_args, ctx, tool)
        try:
            if ctx.tool_call_approved:
                for validator_class in instance.Validators:
                    validator = validator_class.model_validate(
                        instance,
                        from_attributes=True,
                    )
                    validator.validation = validation
                    validator.state = self.state_for(type(instance), validator_class)
                    await self.raise_errors(validator.post_approval)

            run_result = await self.raise_errors(instance.run)
        finally:
            self.validations.pop(ctx.tool_call_id)

        if validation.messages:
            instance.feedback(
                strings.trim(
                    f"The {name} tool completed, but issued the following warnings. Avoid these issues in subsequent calls.",
                    validation.text,
                )
            )

        return run_result
