from __future__ import annotations

from functools import cached_property
from typing import Any, ClassVar, Generic, TypeVar

from cached_classproperty import cached_classproperty
from pydantic import ValidationError
from pydantic_ai import ModelRetry, RunContext, Tool as PydanticTool
from pydantic_ai.tools import ToolDefinition
from pydantic_ai.toolsets import FunctionToolset, ToolsetTool

from corio.iterator import ilist
from corio.strings import get_docstring
from xah.options import base as options
from xah.toolsets.base.approval import (
    ApprovalMetadata,
    ApprovalRequiredToolsetMetadata,
)
from xah.toolsets.base.tool import ToolModel


AgentDepsT = TypeVar("AgentDepsT", contravariant=True)


class Base(FunctionToolset[AgentDepsT], Generic[AgentDepsT]):
    DESCRIPTION: ClassVar[str | None] = None
    TOOLS: ClassVar[tuple[type[ToolModel], ...]] = ()
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

    def __init__(self, **kwargs):
        del kwargs
        super().__init__(id=self.name)
        self.tool_classes: ilist[type[ToolModel]] = ilist(self.TOOLS)
        for tool_class in self.tool_classes:
            self.register(tool_class)

    def register(self, tool_class: type[ToolModel]) -> None:
        async def construct(
            ctx: RunContext[AgentDepsT],
            **tool_args: Any,
        ) -> ToolModel:
            try:
                return tool_class(ctx=ctx, **tool_args)
            except ValidationError as error:
                raise ModelRetry(str(error)) from error

        pydantic_tool = PydanticTool.from_schema(
            function=construct,
            name=tool_class.name,
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

    async def validate(
        self,
        ctx: RunContext[AgentDepsT],
        tool_def: ToolDefinition,
        tool_args: dict[str, Any],
    ) -> ApprovalMetadata:
        tool_class = self.tool_classes.name[tool_def.name]
        try:
            instance = tool_class(ctx=ctx, **tool_args)
        except ValidationError as error:
            raise ModelRetry(str(error)) from error

        messages = await instance.validate()
        return ApprovalMetadata(msgs=messages)

    @cached_property
    def wrapper(self) -> ApprovalRequiredToolsetMetadata[AgentDepsT]:
        return ApprovalRequiredToolsetMetadata(self, self.validate)

    async def call_tool(
        self,
        name: str,
        tool_args: dict[str, Any],
        ctx: RunContext[AgentDepsT],
        tool: ToolsetTool[AgentDepsT],
    ) -> Any:
        instance = await super().call_tool(name, tool_args, ctx, tool)
        return await instance.run()
