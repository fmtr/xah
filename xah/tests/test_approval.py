import asyncio
from functools import cached_property
from types import SimpleNamespace
from typing import ClassVar

import pytest
from pydantic import Field
from pydantic_ai import ApprovalRequired, ModelRetry, RunContext
from pydantic_ai.usage import RunUsage

from corio import Path
from corio.iterator import ilist
from xah.class_collections import classes
from xah.constants import HARNESS_FEEDBACK
from xah.options import base as options
from xah.toolsets.base.tool import Tool
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
        self.messages.append("Approval required")


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
    settings = SimpleNamespace(path=SimpleNamespace(home=Path(".agent")))
    deps = SimpleNamespace(
        toolsets=ilist([toolset]),
        approval_bridge=None,
        settings=settings,
        cwd_default=Path.cwd(),
    )
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
        "messages": {
            "approval": [],
            "decline": [],
            "errors": [],
            "warnings": ["Approval required"],
        },
        "approval": True,
        "abort": False,
    }


def test_approved_call_reuses_tool_and_validator_instances():
    class TrackingValidator(ApprovalWarning):
        instances: ClassVar[list[Tool]] = []

        @classes
        def Validators(cls):
            return []
        approvals: ClassVar[list[Tool]] = []

        def model_post_init(self, context):
            super().model_post_init(context)
            TrackingValidator.instances.append(self)

        async def after_approval(self):
            TrackingValidator.approvals.append(self)

    class TrackingTool(ApprovalTool):
        instances: ClassVar[list[Tool]] = []

        @classes
        def Validators(cls):
            return [TrackingValidator]

        def model_post_init(self, context):
            super().model_post_init(context)
            TrackingTool.instances.append(self)

    class TrackingToolset(ApprovalToolset):
        @classes
        def Tools(cls):
            return [TrackingTool]
    toolset = TrackingToolset()
    ctx = context(toolset)
    tools = asyncio.run(toolset.wrapper.get_tools(ctx))
    name = toolset.tool_name(TrackingTool)
    assert "id" not in TrackingTool.model_json_schema()["properties"]

    with pytest.raises(ApprovalRequired):
        asyncio.run(toolset.wrapper.call_tool(name, {"value": "result"}, ctx, tools[name]))

    instance = toolset.instances.call_id[ctx.tool_call_id]
    validator = instance.validators[0]
    assert instance.call_id == ctx.tool_call_id
    assert validator.call_id == ctx.tool_call_id
    assert TrackingTool.instances == [instance]
    assert TrackingValidator.instances == [validator]

    ctx.tool_call_approved = True
    assert asyncio.run(toolset.wrapper.call_tool(name, {"value": "result"}, ctx, tools[name])) == "result"

    assert TrackingValidator.approvals == [validator]
    assert toolset.instances == []
    assert len(ctx.pending_messages) == 1
    content = ctx.pending_messages[0].messages[0].parts[0].content
    assert content.startswith(HARNESS_FEEDBACK)
    assert "tool completed, but issued the following warnings." in content
    assert "Approval required" in content

def test_decline_hook_uses_retained_tool_and_validator_then_cleans_up():
    class DeclineValidator(ApprovalTool):
        declined_ids: ClassVar[list[str]] = []

        @classes
        def Validators(cls):
            return []

        async def validate(self):
            pass

        async def after_decline(self):
            self.declined_ids.append(self.call_id)

    class DeclineLifecycleTool(ApprovalTool):
        @classes
        def Validators(cls):
            return [DeclineValidator]

    class DeclineLifecycleToolset(ApprovalToolset):
        @classes
        def Tools(cls):
            return [DeclineLifecycleTool]

    toolset = DeclineLifecycleToolset()
    first_ctx = context(toolset, tool_call_id="call-1")
    second_ctx = context(toolset, tool_call_id="call-2")
    tool_def = next(iter(toolset.tools.values())).tool_def
    asyncio.run(toolset.validate(first_ctx, tool_def, {"value": "first"}))
    asyncio.run(toolset.validate(second_ctx, tool_def, {"value": "second"}))

    first_instance = toolset.instances.call_id[first_ctx.tool_call_id]
    second_instance = toolset.instances.call_id[second_ctx.tool_call_id]
    first_validator = first_instance.validators[0]
    second_validator = second_instance.validators[0]
    asyncio.run(toolset.after_decline(first_ctx.tool_call_id))

    assert first_validator.declined_ids == [first_ctx.tool_call_id]
    assert toolset.instances == [second_instance]
    asyncio.run(toolset.after_decline(second_ctx.tool_call_id))
    assert second_validator.declined_ids == [first_ctx.tool_call_id, second_ctx.tool_call_id]
    assert toolset.instances == []


def test_toolset_converts_model_validation_errors_to_model_retry():
    toolset = ApprovalToolset()
    tool_def = next(iter(toolset.tools.values())).tool_def
    with pytest.raises(ModelRetry):
        toolset.init_tool(context(toolset), tool_def, {})


def test_toolset_indexes_instances_by_call_id_when_tool_has_domain_id():
    class DomainIdTool(ApprovalTool):
        id: str = "collection-123"

        @classes
        def Validators(cls):
            return []

    class DomainIdToolset(ApprovalToolset):
        @classes
        def Tools(cls):
            return [DomainIdTool]

    toolset = DomainIdToolset()
    ctx = context(toolset, approved=True)
    tools = asyncio.run(toolset.get_tools(ctx))
    name = toolset.tool_name(DomainIdTool)

    result = asyncio.run(
        toolset.call_tool(name, {"value": "result"}, ctx, tools[name])
    )

    assert result == "result"
    assert toolset.instances == []


def test_full_policy_keeps_warning_messages():
    toolset = ApprovalToolset()
    toolset.options.cls[options.Policy].current_value = options.Policies.FULL
    tool_def = next(iter(toolset.tools.values())).tool_def
    instance = toolset.init_tool(context(toolset), tool_def, {"value": "result"})
    asyncio.run(instance.validate())
    assert instance.validation.messages.warnings == ["Approval required"]


def test_auto_policy_turns_warnings_into_model_retry():
    toolset = ApprovalToolset()
    toolset.options.cls[options.Policy].current_value = options.Policies.AUTO
    ctx = context(toolset)
    tools = asyncio.run(toolset.wrapper.get_tools(ctx))
    name = toolset.tool_name(ApprovalTool)

    with pytest.raises(ModelRetry, match="Approval required"):
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
