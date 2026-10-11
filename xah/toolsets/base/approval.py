from typing import Generic, TypeVar

from pydantic_ai import ApprovalRequired, ApprovalRequiredToolset, WrapperToolset

from xah.toolsets.base.tool import Validation


AgentDepsT = TypeVar("AgentDepsT", contravariant=True)


class ApprovalRequiredToolsetMetadata(
    ApprovalRequiredToolset[AgentDepsT],
    Generic[AgentDepsT],
):
    async def call_tool(self, name, tool_args, ctx, tool):
        """Require approval before delegating to the framework tool call."""
        if not ctx.tool_call_approved:
            validation: Validation = await self.approval_required_func(
                ctx,
                tool.tool_def,
                tool_args,
            )
            if validation:
                raise ApprovalRequired(validation.model_dump())

        return await WrapperToolset.call_tool(
            self,
            name,
            tool_args,
            ctx,
            tool,
        )
