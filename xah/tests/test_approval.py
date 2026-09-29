import asyncio
from functools import cached_property
from types import SimpleNamespace

import pytest
from cached_classproperty import cached_classproperty
from pydantic import Field
from pydantic_ai import ApprovalRequired, ModelRetry, RunContext
from pydantic_ai.usage import RunUsage

from corio.iterator import ilist
from xah.options import base as options
from xah.toolsets.base.tool import Tool, ValidationResult
from xah.toolsets.base.toolset import Toolset


class ApprovalTool(Tool):
    value: str = Field(description="Value returned by the tool.")

    @cached_classproperty
    def VALIDATORS(cls):
        return [ApprovalWarning]

    async def run(self) -> str:
        return self.value


class ApprovalWarning(ApprovalTool):
    async def validate(self, result: ValidationResult):
        result.messages.append("Approval required")


class ApprovalToolset(Toolset):
    @cached_classproperty
    def TOOLS(cls):
        return [ApprovalTool]

    @cached_property
    def options(self):
        return ilist([options.Policy.from_value(self.name, options.APPROVAL)])


class ReplacementWarning(ApprovalWarning):
    NAME = ApprovalWarning.local_name


class ReplacementApprovalTool(ApprovalTool):
    NAME = ApprovalTool.local_name

    @cached_classproperty
    def VALIDATORS(cls):
        return [ReplacementWarning]


class ReplacementApprovalToolset(ApprovalToolset):
    @cached_classproperty
    def TOOLS(cls):
        return {ReplacementApprovalTool: True}


class SecondaryTool(ApprovalTool):
    pass


class SecondaryToolset(Toolset):
    @cached_classproperty
    def TOOLS(cls):
        return [SecondaryTool]


class CombinedToolset(ApprovalToolset, SecondaryToolset):
    @cached_classproperty
    def TOOLS(cls):
        return {ApprovalTool: False}


def context(toolset, approved=False):
    deps = SimpleNamespace(toolsets=ilist([toolset]))
    return RunContext(deps=deps, model=None, usage=RunUsage(), tool_call_approved=approved)


def test_declarative_collections_merge_replace_and_remove_by_name():
    replacement = ReplacementApprovalToolset()
    combined = CombinedToolset()
    instance = ReplacementApprovalTool(
        ctx=context(replacement),
        toolset=replacement,
        value="result",
    )

    assert replacement.tool_classes == [ReplacementApprovalTool]
    assert instance.validator_classes == [ReplacementWarning]
    assert combined.tool_classes == [SecondaryTool]


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
    assert asyncio.run(toolset.wrapper.call_tool(name, {"value": "result"}, ctx, tools[name])) == "result\n\nWarnings:\nApproval required"

def test_toolset_converts_model_validation_errors_to_model_retry():
    toolset = ApprovalToolset()
    tool_def = next(iter(toolset.tools.values())).tool_def
    with pytest.raises(ModelRetry):
        toolset.init_tool(context(toolset), tool_def, {})


def test_full_policy_keeps_warning_messages():
    toolset = ApprovalToolset()
    toolset.options.cls[options.Policy].current_value = options.FULL
    tool_def = next(iter(toolset.tools.values())).tool_def
    instance = toolset.init_tool(context(toolset), tool_def, {"value": "result"})
    result = ValidationResult()
    asyncio.run(instance.validate(result))
    assert result.messages == ["Approval required"]


def test_auto_policy_turns_warnings_into_model_retry():
    toolset = ApprovalToolset()
    toolset.options.cls[options.Policy].current_value = options.AUTO
    ctx = context(toolset)
    tools = asyncio.run(toolset.wrapper.get_tools(ctx))
    name = toolset.tool_name(ApprovalTool)

    with pytest.raises(ApprovalRequired):
        asyncio.run(toolset.wrapper.call_tool(name, {"value": "result"}, ctx, tools[name]))


def test_full_policy_runs_and_reports_warnings():
    toolset = ApprovalToolset()
    toolset.options.cls[options.Policy].current_value = options.FULL
    ctx = context(toolset)
    tools = asyncio.run(toolset.wrapper.get_tools(ctx))
    name = toolset.tool_name(ApprovalTool)

    result = asyncio.run(toolset.wrapper.call_tool(name, {"value": "result"}, ctx, tools[name]))

    assert result == "result\n\nWarnings:\nApproval required"
