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
from xah.toolsets.base.approval import ApprovalMetadata
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.toolset import Base


class ApprovalTool(Tool):
    value: str = Field(description="Value returned by the tool.")

    @cached_classproperty
    def VALIDATORS(cls):
        return [ApprovalWarning]

    async def run(self) -> str:
        return self.value


class ApprovalWarning(ApprovalTool):
    async def validate(self) -> list[str]:
        return ["Approval required"]


class ApprovalToolset(Base):
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


class SecondaryToolset(Base):
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
    assert error.value.metadata == {"msgs": ["Approval required"]}


def test_approved_call_constructs_a_fresh_model_and_runs_it():
    toolset = ApprovalToolset()
    ctx = context(toolset, approved=True)

    async def call():
        tools = await toolset.wrapper.get_tools(ctx)
        name = toolset.tool_name(ApprovalTool)
        return await toolset.wrapper.call_tool(name, {"value": "result"}, ctx, tools[name])

    assert asyncio.run(call()) == "result"


def test_approval_metadata_truth_tracks_messages():
    assert not ApprovalMetadata()
    assert ApprovalMetadata(msgs=["Approval required"])


def test_toolset_converts_model_validation_errors_to_model_retry():
    toolset = ApprovalToolset()
    tool_def = next(iter(toolset.tools.values())).tool_def
    with pytest.raises(ModelRetry):
        asyncio.run(toolset.validate(context(toolset), tool_def, {}))


def test_full_policy_disables_default_approval_validator():
    toolset = ApprovalToolset()
    toolset.options.cls[options.Policy].current_value = options.FULL
    tool_def = next(iter(toolset.tools.values())).tool_def
    metadata = asyncio.run(toolset.validate(context(toolset), tool_def, {"value": "result"}))
    assert not metadata
