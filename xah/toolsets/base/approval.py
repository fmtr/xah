from __future__ import annotations

from functools import cached_property
from typing import Generic, Self, TypeVar

from pydantic import Field
from pydantic_ai import ApprovalRequired, ApprovalRequiredToolset, WrapperToolset

from corio import dm


class ApprovalMetadata(dm.Base):
    msgs: list[str] = Field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.msgs)

    @cached_property
    def text(self) -> str:
        return "\n".join(self.msgs)

    @classmethod
    def from_bool(cls, value: bool) -> Self:
        if value:
            return cls(msgs=["Approval required"])
        return cls()


AgentDepsT = TypeVar("AgentDepsT", contravariant=True)


class ApprovalRequiredToolsetMetadata(
    ApprovalRequiredToolset[AgentDepsT],
    Generic[AgentDepsT],
):
    async def call_tool(self, name, tool_args, ctx, tool):
        metadata = None
        if not ctx.tool_call_approved:
            metadata = await self.approval_required_func(
                ctx,
                tool.tool_def,
                tool_args,
            )
            if isinstance(metadata, bool):
                metadata = ApprovalMetadata.from_bool(metadata)

        if metadata:
            raise ApprovalRequired(metadata.model_dump())

        return await WrapperToolset.call_tool(
            self,
            name,
            tool_args,
            ctx,
            tool,
        )
