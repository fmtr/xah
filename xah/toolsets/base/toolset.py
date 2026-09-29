from __future__ import annotations

from functools import cached_property
from typing import Any, ClassVar, Generic, TypeVar

from cached_classproperty import cached_classproperty
from pydantic import ValidationError
from pydantic_ai import ModelRetry, RunContext, Tool as PydanticTool
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import FunctionToolset, ToolsetTool

from corio import strings
from corio.iterator import ilist
from corio.strings import get_docstring
from xah.class_collections import ClassDeclaration, resolve_class_collection
from xah.options import base as options
from xah.toolsets.base.approval import ApprovalRequiredToolsetMetadata
from xah.toolsets.base.tool import Tool, ValidationResult


AgentDepsT = TypeVar("AgentDepsT", contravariant=True)


class Toolset(FunctionToolset[AgentDepsT], Generic[AgentDepsT]):
    DESCRIPTION: ClassVar[str | None] = None
    POLICY: ClassVar[str] = options.FULL

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
        return None

    @cached_classproperty
    def TOOLS(cls) -> ClassDeclaration[Tool]:
        return []

    @cached_property
    def tool_classes(self) -> ilist[type[Tool]]:
        return resolve_class_collection(type(self), "TOOLS", "local_name")

    def __init__(self, **kwargs):
        del kwargs
        super().__init__(id=self.name)
        for tool_class in self.tool_classes:
            self.register(tool_class)

    def tool_name(self, tool_class: type[Tool]) -> str:
        return f"{self.name}-{tool_class.local_name}"

    def local_tool_name(self, name: str) -> str:
        return name.removeprefix(f"{self.name}-")

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
                return tool_class(ctx=ctx, toolset=self, **tool_args)
            except ValidationError as error:
                raise ModelRetry(str(error)) from error

        pydantic_tool = PydanticTool.from_schema(
            function=construct,
            name=self.tool_name(tool_class),
            description=tool_class.description,
            json_schema=tool_class.model_json_schema(),
            takes_ctx=True,
        )
        self.add_tool(pydantic_tool)

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
    def validation_results(self) -> dict[str | None, ValidationResult]:
        return {}

    def init_tool(
        self,
        ctx: RunContext[AgentDepsT],
        tool_def: ToolDefinition,
        tool_args: dict[str, Any],
    ) -> Tool:
        """
        Initialize a temporary tool for preflight inspection.

        This direct constructor is separate from the registered constructor
        used by Pydantic AI during execution because approval runs before the
        framework dispatches the tool.
        """
        local_name = self.local_tool_name(tool_def.name)
        tool_class = self.tool_classes.local_name[local_name]
        try:
            return tool_class(ctx=ctx, toolset=self, **tool_args)
        except ValidationError as error:
            raise ModelRetry(str(error)) from error

    async def validate(
        self,
        ctx: RunContext[AgentDepsT],
        tool_def: ToolDefinition,
        tool_args: dict[str, Any],
    ) -> ValidationResult:
        instance = self.init_tool(ctx, tool_def, tool_args)
        result = ValidationResult(
            approval=instance.approval,
            raise_for_messages=instance.raise_on_warn,
        )
        await instance.validate(result)
        self.validation_results[ctx.tool_call_id] = result
        return result

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
        instance = await super().call_tool(name, tool_args, ctx, tool)
        validation = self.validation_results.pop(ctx.tool_call_id)
        result = await instance.run()
        if not validation.messages:
            return result

        return strings.trim(
            f"""
            {result}

            # Warnings
            
            The tool completed, but issued the following warnings. Avoid these issues in subsequent calls.
            """,
            validation.text
        )
