import asyncio
from functools import cached_property
from types import SimpleNamespace

import pytest
from pydantic import Field
from pydantic_ai import ApprovalRequired, ModelRetry, RunContext
from pydantic_ai.usage import RunUsage

from corio.iterator import ilist
from xah.class_collections import classes
from xah.constants import HARNESS_FEEDBACK
from xah.options import base as options
from xah.toolsets.base.tool import Tool, Validation
from xah.toolsets.base.toolset import Toolset


class ApprovalTool(Tool):
    value: str = Field(description="Value returned by the tool.")

    @classes
    def Validators(cls):
        return [ApprovalWarning]

    async def run(self) -> str:
        return self.value


class ApprovalWarning(ApprovalTool):
    async def validate(self):
        self.validation.messages.append("Approval required")


class ApprovalToolset(Toolset):
    @classes
    def Tools(cls):
        return [ApprovalTool]

    @cached_property
    def options(self):
        return ilist([options.Policy.from_value(self.name, options.Policies.APPROVAL)])


class ReplacementWarning(ApprovalWarning):
    NAME = ApprovalWarning.local_name


class ReplacementApprovalTool(ApprovalTool):
    NAME = ApprovalTool.local_name

    @classes
    def Validators(cls):
        return [ReplacementWarning]


class ReplacementApprovalToolset(ApprovalToolset):
    @classes
    def Tools(cls):
        return [ReplacementApprovalTool]


class SecondaryTool(ApprovalTool):
    pass


class SecondaryToolset(Toolset):
    @classes
    def Tools(cls):
        return [SecondaryTool]


class CombinedToolset(ApprovalToolset, SecondaryToolset):
    @classes
    def Tools(cls):
        return [SecondaryTool]


def context(toolset, approved=False, tool_call_id="call-1"):
    deps = SimpleNamespace(toolsets=ilist([toolset]))
    return RunContext(
        deps=deps,
        model=None,
        usage=RunUsage(),
        tool_call_approved=approved,
        pending_messages=[],
        tool_call_id=tool_call_id,
    )


def test_tool_feedback_enqueues_system_prompt():
    toolset = ApprovalToolset()
    ctx = context(toolset)
    instance = ApprovalTool(ctx=ctx, toolset=toolset, value="result")

    instance.feedback("Keep the next call focused.")

    content = ctx.pending_messages[0].messages[0].parts[0].content
    assert content.startswith(HARNESS_FEEDBACK)
    assert "ApprovalToolset-ApprovalTool (call-1) reported:" in content
    assert content.endswith("Keep the next call focused.")


def test_declarative_collections_merge_replace_and_remove_by_name():
    replacement = ReplacementApprovalToolset()
    combined = CombinedToolset()
    instance = ReplacementApprovalTool(
        ctx=context(replacement),
        toolset=replacement,
        value="result",
    )

    assert replacement.Tools == [ReplacementApprovalTool]
    assert type(instance).Validators == [ReplacementWarning]
    assert combined.Tools == [SecondaryTool]


def test_local_approval_wrapper_serializes_validator_messages():
    toolset = ApprovalToolset()
    ctx = context(toolset)

    async def call():
        tools = await toolset.wrapper.get_tools(ctx)
        name = toolset.tool_name(ApprovalTool)
        return await toolset.wrapper.call_tool(name, {"value": "result"}, ctx, tools[name])

    with pytest.raises(ApprovalRequired) as error:
        asyncio.run(call())
    assert error.value.metadata == {
        "messages": ["Approval required"],
        "approval": True,
        "raise_for_messages": False,
    }


def test_approved_call_constructs_a_fresh_model_and_runs_it():
    toolset = ApprovalToolset()
    ctx = context(toolset)
    tools = asyncio.run(toolset.wrapper.get_tools(ctx))
    name = toolset.tool_name(ApprovalTool)

    with pytest.raises(ApprovalRequired):
        asyncio.run(toolset.wrapper.call_tool(name, {"value": "result"}, ctx, tools[name]))

    ctx.tool_call_approved = True
    assert asyncio.run(toolset.wrapper.call_tool(name, {"value": "result"}, ctx, tools[name])) == "result"
    assert len(ctx.pending_messages) == 1
    content = ctx.pending_messages[0].messages[0].parts[0].content
    assert content.startswith(HARNESS_FEEDBACK)
    assert "tool completed, but issued the following warnings." in content
    assert "Approval required" in content

def test_toolset_converts_model_validation_errors_to_model_retry():
    toolset = ApprovalToolset()
    tool_def = next(iter(toolset.tools.values())).tool_def
    with pytest.raises(ModelRetry):
        toolset.init_tool(context(toolset), tool_def, {}, Validation())


def test_full_policy_keeps_warning_messages():
    toolset = ApprovalToolset()
    toolset.options.cls[options.Policy].current_value = options.Policies.FULL
    tool_def = next(iter(toolset.tools.values())).tool_def
    result = Validation()
    instance = toolset.init_tool(context(toolset), tool_def, {"value": "result"}, result)
    asyncio.run(instance.validate())
    assert result.messages == ["Approval required"]


def test_auto_policy_turns_warnings_into_model_retry():
    toolset = ApprovalToolset()
    toolset.options.cls[options.Policy].current_value = options.Policies.AUTO
    ctx = context(toolset)
    tools = asyncio.run(toolset.wrapper.get_tools(ctx))
    name = toolset.tool_name(ApprovalTool)

    with pytest.raises(ApprovalRequired):
        asyncio.run(toolset.wrapper.call_tool(name, {"value": "result"}, ctx, tools[name]))


def test_full_policy_runs_and_reports_warnings():
    toolset = ApprovalToolset()
    toolset.options.cls[options.Policy].current_value = options.Policies.FULL
    ctx = context(toolset)
    tools = asyncio.run(toolset.wrapper.get_tools(ctx))
    name = toolset.tool_name(ApprovalTool)

    result = asyncio.run(toolset.wrapper.call_tool(name, {"value": "result"}, ctx, tools[name]))

    assert result == "result"
    assert len(ctx.pending_messages) == 1
