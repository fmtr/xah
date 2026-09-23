import asyncio
from functools import cached_property
from types import SimpleNamespace
from typing import ClassVar

import pytest
from cached_classproperty import cached_classproperty
from pydantic import Field
from pydantic_ai import ApprovalRequired, ModelRetry, RunContext
from pydantic_ai.usage import RunUsage

from xah.options import base as options
from corio.iterator import ilist
from xah.toolsets.base.approval import ApprovalMetadata
from xah.toolsets.base.sig import Sig
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.toolset import Base
from xah.toolsets.base.validator import Validator


class ApprovalSig(Sig):
    value: str = Field(description="Value returned by the tool.")

    @cached_classproperty
    def toolset_type(cls):
        return ApprovalToolset


class ApprovalWarning(Validator, ApprovalSig):
    async def validate(self) -> list[str]:
        return ["Approval required"]


class ApprovalTool(Tool, ApprovalSig):
    VALIDATORS: ClassVar = (ApprovalWarning,)

    async def run(self) -> str:
        return self.value


class ApprovalToolset(Base):
    TOOLS = (ApprovalTool,)

    @cached_property
    def options(self):
        return ilist([options.Policy.from_value(self.name, options.APPROVAL)])


def context(toolset, approved=False):
    deps = SimpleNamespace(toolsets=ilist([toolset]))
    return RunContext(deps=deps, model=None, usage=RunUsage(), tool_call_approved=approved)


def test_local_approval_wrapper_serializes_validator_messages():
    toolset = ApprovalToolset()
    ctx = context(toolset)

    async def call():
        tools = await toolset.wrapper.get_tools(ctx)
        return await toolset.wrapper.call_tool(ApprovalTool.name, {"value": "result"}, ctx, tools[ApprovalTool.name])

    with pytest.raises(ApprovalRequired) as error:
        asyncio.run(call())
    assert error.value.metadata == {"msgs": ["Approval required"]}


def test_approved_call_constructs_a_fresh_model_and_runs_it():
    toolset = ApprovalToolset()
    ctx = context(toolset, approved=True)

    async def call():
        tools = await toolset.wrapper.get_tools(ctx)
        return await toolset.wrapper.call_tool(ApprovalTool.name, {"value": "result"}, ctx, tools[ApprovalTool.name])

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
