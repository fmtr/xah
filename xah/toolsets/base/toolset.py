from __future__ import annotations

from functools import cached_property
from typing import Any, ClassVar, Generic, TypedDict, TypeVar

from cached_classproperty import cached_classproperty
from pydantic import BaseModel, ValidationError, ConfigDict
from pydantic_ai import ModelRetry, RunContext, Tool as PydanticTool, ToolFailed
from pydantic_ai.exceptions import UserError
from pydantic_ai.messages import InstructionPart, SystemPromptPart
from pydantic_ai.tools import ToolDefinition
from acp.schema import ToolCallStatus
from pydantic_acp import ProjectionMap
from pydantic_acp.projection import ToolProjection
from pydantic_ai.toolsets import FunctionToolset, ToolsetTool

from corio import Path, jsn, strings
from corio.function import ccp, cp
from corio.iterator import ilist
from corio.tools import Empty
from corio.strings import get_docstring
from xah.class_collections import classes
from xah.constants import HARNESS_FEEDBACK
from xah.obs import logger
from xah.options import base as options
from xah.toolsets.base.approval import ApprovalRequiredToolsetMetadata
from xah.toolsets.base.projection import Projection
from xah.toolsets.base.tool import Kinds, Tool, ToolState, Validation


AgentDepsT = TypeVar("AgentDepsT", contravariant=True)


class ToolsetInfo(TypedDict):
    active: bool
    name: str
    desc: str | None
    protected: bool
    tools: list[str]


class Toolset(FunctionToolset[AgentDepsT], Generic[AgentDepsT]):

    model_config = ConfigDict(ignored_types=(cached_classproperty,))

    DESCRIPTION: ClassVar[str | None] = None
    IS_MANAGEMENT: ClassVar[bool] = False
    POLICY: ClassVar[str] = options.Policy.Policies.AUTO
    MAX_INLINE_OUTPUT_LENGTH: ClassVar[int] = 50_000

    @cached_classproperty
    def name(cls) -> str:
        return cls.__name__

    @ccp
    def prefix(cls) -> str:
        return f"{cls.name}-"

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
            tools=[tool_class.suffix for tool_class in self.Tools],
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

    @ccp
    def maps(cls) -> list[ProjectionMap]:
        return [cls]

    @classmethod
    def get_name(cls, tool_class: type[Tool]) -> str:
        return f"{cls.prefix}{tool_class.suffix}"

    @classmethod
    def get_suffix(cls, name: str) -> str:
        return name.removeprefix(cls.prefix)

    @classmethod
    def get_tool(cls, name: str, default=Empty) -> Any:
        if name.startswith(cls.prefix):
            suffix = cls.get_suffix(name)
        elif "-" in name:
            if default is Empty:
                raise KeyError(name)
            return default
        else:
            suffix = name

        if default is Empty:
            return cls.Tools.suffix[suffix]
        return cls.Tools.suffix.get(suffix, default)

    @classmethod
    def kind_for(cls, tool_name: str) -> Kinds | None:
        tool_class = cls.get_tool(tool_name, None)
        if tool_class is None:
            return None
        return tool_class.KIND

    @classmethod
    def project_start(
        cls,
        tool_name: str,
        *,
        cwd: Path | None = None,
        raw_input: Any = None,
    ) -> ToolProjection | None:
        tool_class = cls.get_tool(tool_name, None)
        if tool_class is None:
            return None

        projection_class = tool_class.projections[0]
        projection = projection_class(
            tool_cls=tool_class,
            toolset_cls=cls,
            raw_input=raw_input,
            cwd=cwd,
        )
        return projection.start()

    @classmethod
    def project_progress(
        cls,
        tool_name: str,
        *,
        cwd: Path | None = None,
        raw_input: Any = None,
        raw_output: Any = None,
        serialized_output: str,
        status: ToolCallStatus,
    ) -> ToolProjection | None:
        tool_class = cls.get_tool(tool_name, None)
        if tool_class is None:
            return None

        projection_class = tool_class.projections[0]
        projection = projection_class(
            tool_cls=tool_class,
            toolset_cls=cls,
            raw_input=raw_input,
            cwd=cwd,
            raw_output=raw_output,
            serialized_output=serialized_output,
            status=status,
        )
        return projection.progress()

    def __init__(self, activated: bool = True, **kwargs):
        del kwargs
        self.activated = activated
        super().__init__(id=self.name)
        for tool_class in self.Tools:
            self.register(tool_class)

    @staticmethod
    def feedback(ctx: RunContext, message: str | SystemPromptPart) -> str | None:
        if isinstance(message, str):
            message = strings.trim(HARNESS_FEEDBACK, message)
            message = SystemPromptPart(content=message)

        try:
            return ctx.enqueue(message)
        except UserError:
            logger.warning(
                f"Toolset feedback occurred after the agent run completed: {message.content}"
            )

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
            return self.instances.call_id[ctx.tool_call_id]

        pydantic_tool = PydanticTool.from_schema(
            function=get_instance,
            name=self.get_name(tool_class),
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
        tool_class = self.get_tool(tool_def.name)
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
        instance = self.instances.call_id[tool_call_id]
        try:
            await self.raise_errors(instance.after_decline)
            for validator in instance.validators:
                await self.raise_errors(validator.after_decline)
        finally:
            self.instances.remove(instance)

    @staticmethod
    def serialize_output(result: Any) -> Any:
        if isinstance(result, BaseModel):
            return result.model_dump(mode="json")

        if isinstance(result, list):
            return [Toolset.serialize_output(item) for item in result]

        if isinstance(result, dict):
            return {key: Toolset.serialize_output(value) for key, value in result.items()}

        return result

    def externalize_output(self, instance: Tool, result: Any) -> Any:
        if not instance.EXTERNALIZE_OUTPUT:
            return result

        if isinstance(result, str):
            suffix = "txt"
            serialized = result
        else:
            suffix = "json"
            data = self.serialize_output(result)
            serialized = jsn.to_json(data)

        if len(serialized) <= self.MAX_INLINE_OUTPUT_LENGTH:
            return result

        settings = instance.ctx.deps.settings
        directory = instance.ctx.deps.cwd_default / settings.path.home.name / "artifacts"
        directory.mkdirf()
        artifact = directory / f"{instance.call_id}.{suffix}"
        artifact.write_text(serialized)

        return strings.trim(f"""
            Tool produced too much output.
            Use regular file tools to inspect the full output: {artifact}
        """)

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[AgentDepsT],
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        """Execute the retained tool instance after validation and approval."""
        if ctx.tool_call_id not in self.instances.call_id:
            await self.validate(ctx, tool.tool_def, tool_args)
        instance = self.instances.call_id[ctx.tool_call_id]
        try:
            instance = await super().call_tool(name, tool_args, ctx, tool)
            if ctx.tool_call_approved:
                await self.after_approval(instance)

            run_result = await self.raise_errors(instance.run)
        finally:
            self.instances.remove(instance)

        if instance.validation.messages.warnings:
            instance.feedback(
                strings.trim(
                    f"The {name} tool completed, but issued the following warnings. Avoid these issues in subsequent calls.",
                    instance.validation.messages.warnings.text,
                )
            )

        return self.externalize_output(instance, run_result)
