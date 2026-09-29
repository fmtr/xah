from typing import Generic, TypeVar

from pydantic_ai import ApprovalRequired, ApprovalRequiredToolset, WrapperToolset


AgentDepsT = TypeVar("AgentDepsT", contravariant=True)


class ApprovalRequiredToolsetMetadata(
    ApprovalRequiredToolset[AgentDepsT],
    Generic[AgentDepsT],
):
    async def call_tool(self, name, tool_args, ctx, tool):
        """Require approval before delegating to the framework tool call."""
        if not ctx.tool_call_approved:
            requires_approval = await self.approval_required_func(
                ctx,
                tool.tool_def,
                tool_args,
            )
            if requires_approval:
                raise ApprovalRequired

        return await WrapperToolset.call_tool(
            self,
            name,
            tool_args,
            ctx,
            tool,
        )
