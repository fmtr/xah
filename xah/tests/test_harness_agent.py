import asyncio
from types import SimpleNamespace

import pytest
from corio import Path
from pydantic_ai import ModelRetry, RunContext
from fastmcp import FastMCP
from pydantic_ai.messages import ToolReturnPart
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage
from pydantic_acp import compose_projection_maps

from xah.class_collections import classes
from xah.harness.base import Harness, HarnessAcp, HarnessBase
from corio.iterator import ilist

from xah.harness.deps import HarnessAgentDeps, HarnessDeps
from xah.options import base as options
from xah.toolsets.base.mcp import ToolsetMCP
from xah.toolsets.base.toolset import Toolset
from xah.toolsets.fs.toolset import Files
from xah.toolsets.shell.toolset import Shell
from xah.toolsets.todo.toolset import Todo
from xah.toolsets.management.activate import (
    Activate,
    ActivationOutput,
    ApproveRequestables,
)
from xah.harness.manager import ToolsetsManager, ToolsetsManagerAgent
from xah.toolsets.management.toolset import Management


def test_harness_base_is_directly_usable():
    agent = HarnessBase(
        model=TestModel(),
        cwd_default=Path.cwd(),
        settings=SimpleNamespace(),
    )

    assert isinstance(agent.deps, HarnessAgentDeps)
    assert agent.deps.toolsets.all == []
    assert agent.agent_capabilities == [
        agent.stuck_loop_detection,
        agent.model_traffic_logger,
    ]


def test_harness_deps_adds_approval_behavior_to_agent_deps():
    assert issubclass(HarnessDeps, HarnessAgentDeps)
    assert Harness is not HarnessAcp


def make_agent_deps(toolset_classes):
    return HarnessAgentDeps(
        settings=SimpleNamespace(),
        cwd_default=Path.cwd(),
        toolsets_classes=toolset_classes,
    )


def make_acp_deps(toolset_classes):
    return HarnessDeps(
        settings=SimpleNamespace(),
        cwd_default=Path.cwd(),
        toolsets_classes=toolset_classes,
    )


@pytest.fixture
def mcp_server():
    server = FastMCP("synthetic-service")
    calls = []

    @server.tool
    def sample_signal() -> str:
        calls.append("invoked")
        return "synthetic-payload"

    return server, calls


def test_mcp_toolset_noops_projection_lookups(mcp_server):
    server, _ = mcp_server

    class SampleMCP(ToolsetMCP):
        URL = server

    projection_map = compose_projection_maps([SampleMCP])

    assert SampleMCP.get_tool("remote_lookup", None) is None
    assert projection_map.project_start("remote_lookup", raw_input={}) is None
    assert (
        projection_map.project_progress(
            "remote_lookup",
            raw_input={},
            raw_output={},
            serialized_output="{}",
            status="completed",
        )
        is None
    )


def test_agent_deps_constructs_the_configured_toolsets_once():
    deps = make_agent_deps([Files, Shell])

    assert isinstance(deps.toolsets, ToolsetsManagerAgent)
    assert [toolset.name for toolset in deps.toolsets.all] == ["Files", "Shell"]
    assert deps.toolsets is deps.toolsets
    assert deps.toolsets.all.cls[Files] is deps.toolsets.all.name["Files"]
    assert deps.toolsets.all.cls[Shell] is deps.toolsets.all.name["Shell"]


def test_agent_deps_toolsets_are_constructed_from_the_declared_classes():
    class CustomToolset(Toolset):
        pass

    deps = make_agent_deps([CustomToolset])

    assert deps.toolsets.all.cls[CustomToolset].name == "CustomToolset"
    assert type(deps.toolsets.all[0]) is CustomToolset


def test_basic_agent_toolset_combination_uses_all_configured_toolsets():
    deps = make_agent_deps([Files, Shell])
    context = SimpleNamespace(deps=deps)

    combined = HarnessAgentDeps.get_toolset(context)

    assert {tool.id for tool in combined.toolsets} == {"Files", "Shell"}


def test_agent_manager_separates_mcp_instances_and_composes_them(mcp_server):
    server, _ = mcp_server

    class SampleMCP(ToolsetMCP):
        URL = server

    deps = make_agent_deps([Files, SampleMCP])
    manager = deps.toolsets
    mcp = manager.mcp[0]

    assert manager.mcp is manager.mcp
    assert isinstance(mcp, SampleMCP)
    assert mcp.id == SampleMCP.__name__
    assert mcp.settings is deps.settings
    assert mcp.client is not SampleMCP().client
    assert mcp in manager.all
    assert mcp.activated
    assert mcp in manager.combined.toolsets
    assert manager.all.cls[Files] in manager.combined.toolsets


def test_acp_manager_combines_policy_wrappers_with_native_mcp(mcp_server):
    server, _ = mcp_server

    class SampleMCP(ToolsetMCP):
        URL = server

    manager = make_acp_deps([Files, SampleMCP]).toolsets
    mcp = manager.mcp[0]

    assert mcp in manager.all
    assert mcp.activated
    assert mcp in manager.combined.toolsets
    assert manager.all.cls[Files].wrapper in manager.combined.toolsets

    manager.all.cls[Files].options.cls[options.Policy].current_value = (
        options.Policies.DISABLED
    )
    assert manager.wrapped == []
    assert mcp in manager.combined.toolsets

    mcp.options.cls[options.Policy].current_value = options.Policies.DISABLED
    assert mcp not in manager.permitted
    assert mcp not in manager.combined.toolsets


def test_acp_combined_toolset_exposes_tools_and_instructions():
    manager = make_acp_deps([Management, Files]).toolsets
    context = RunContext(
        deps=SimpleNamespace(toolsets=manager),
        model=TestModel(),
        usage=RunUsage(),
    )

    async def inspect_combined():
        combined = manager.combined
        tools = await combined.get_tools(context)
        instructions = await combined.get_instructions(context)
        return tools, instructions

    tools, instructions = asyncio.run(inspect_combined())

    instruction_text = " ".join(part.content for part in instructions)

    assert set(tools) == {Management.get_name(Activate)}
    assert Files.name in instruction_text


def test_harness_agent_discovers_and_runs_native_mcp_tool(mcp_server):
    server, calls = mcp_server

    class SampleMCP(ToolsetMCP):
        URL = server

    class SampleHarness(HarnessBase):
        @classes
        def Instructions(cls):
            return []

        @classes
        def Toolsets(cls):
            return [SampleMCP]

    harness = SampleHarness(
        model=TestModel(),
        cwd_default=Path.cwd(),
        settings=SimpleNamespace(),
    )

    mcp = harness.deps.toolsets.mcp[0]
    assert mcp.activated
    result = asyncio.run(
        harness.agent.run("Inspect the sample signal.", deps=harness.deps)
    )
    tool_returns = [
        part
        for message in result.all_messages()
        for part in message.parts
        if isinstance(part, ToolReturnPart)
    ]

    assert calls == ["invoked"]
    assert any("sample_signal" in part.tool_name for part in tool_returns)
    assert any("synthetic-payload" in str(part.content) for part in tool_returns)
    assert mcp.client is mcp.client
    assert not mcp.is_running


def test_acp_permitted_toolsets_follow_policy_state():
    deps = make_acp_deps([Files, Shell])
    files = deps.toolsets.all.cls[Files]
    shell = deps.toolsets.all.cls[Shell]

    assert deps.toolsets.permitted == ilist([files, shell])
    assert {wrapped.wrapped for wrapped in deps.toolsets.wrapped} == {files, shell}

    shell.options.cls[options.Policy].current_value = options.Policies.FULL

    assert deps.toolsets.permitted == ilist([files, shell])
    assert {wrapped.wrapped for wrapped in deps.toolsets.wrapped} == {files, shell}

    files.options.cls[options.Policy].current_value = options.Policies.DISABLED

    assert deps.toolsets.permitted == ilist([shell])
    assert deps.toolsets.wrapped == [shell.wrapper]


def test_acp_toolset_options_include_configured_toolsets_even_when_disabled(mcp_server):
    server, _ = mcp_server

    class SampleMCP(ToolsetMCP):
        URL = server

    deps = make_acp_deps([Todo, Shell, SampleMCP])
    shell = deps.toolsets.all.cls[Shell]
    mcp = deps.toolsets.all.cls[SampleMCP]

    shell.options.cls[options.Policy].current_value = options.Policies.DISABLED
    mcp.options.cls[options.Policy].current_value = options.Policies.DISABLED

    assert "Todo/Policy" in deps.options.name
    assert "Shell/Policy" in deps.options.name
    assert "SampleMCP/Policy" in deps.options.name
    assert shell not in deps.toolsets.permitted
    assert mcp not in deps.toolsets.permitted


def test_toolset_instances_are_shared_by_options_and_toolset_lookup():
    deps = make_acp_deps([Todo])
    todo_from_lookup = deps.toolsets.all.name[Todo.name]
    todo_from_options = next(
        toolset
        for toolset in deps.toolsets.all
        if toolset.name == Todo.name
    )

    assert todo_from_lookup is todo_from_options
    assert todo_from_lookup.options.cls[options.Policy] is deps.options.name["Todo/Policy"]


def test_toolsets_management_marker_is_explicit():
    assert Management.IS_MANAGEMENT
    assert not Files.IS_MANAGEMENT


def test_agent_toolsets_manager_activates_all_without_management():
    parent = SimpleNamespace(
        settings=SimpleNamespace(),
        cwd_default=Path.cwd(),
        toolsets_classes=[Files, Shell],
    )
    manager = ToolsetsManagerAgent(parent)

    assert not manager.is_managed
    assert [toolset.name for toolset in manager.all] == ["Files", "Shell"]
    assert manager.activated == manager.all
    assert manager.permitted == manager.all
    assert {type(toolset) for toolset in manager.agent} == {Files, Shell}


def test_agent_toolsets_manager_only_activates_management_initially():
    parent = SimpleNamespace(
        settings=SimpleNamespace(),
        cwd_default=Path.cwd(),
        toolsets_classes=[Management, Files],
    )
    manager = ToolsetsManagerAgent(parent)

    assert manager.is_managed
    assert manager.all.name[Management.name].activated
    assert not manager.all.name[Files.name].activated
    assert manager.agent == ilist([manager.all.name[Management.name]])


def test_acp_toolsets_manager_applies_policy_after_activation():
    parent = SimpleNamespace(
        settings=SimpleNamespace(),
        cwd_default=Path.cwd(),
        toolsets_classes=[Files, Shell],
    )
    manager = ToolsetsManager(parent)
    shell = manager.all.name[Shell.name]

    assert manager.permitted == ilist([manager.all.name[Files.name], shell])
    assert set(manager.agent) == {manager.all.name[Files.name], shell}

    shell.options.cls[options.Policy].current_value = options.Policies.FULL
    assert manager.permitted == manager.all
    assert {type(toolset) for toolset in manager.agent} == {Files, Shell}

    manager.all.name[Files.name].activated = False
    assert manager.agent == ilist([shell])


def test_mcp_toolsets_use_the_shared_activation_and_policy_contract(mcp_server):
    server, _ = mcp_server

    class SampleMCP(ToolsetMCP):
        URL = server

    manager = make_acp_deps([Management, SampleMCP]).toolsets
    management = manager.all.name[Management.name]
    mcp = manager.all.name[SampleMCP.name]
    context = RunContext(
        deps=SimpleNamespace(toolsets=manager),
        model=TestModel(),
        usage=RunUsage(),
    )
    activation = Activate(
        ctx=context,
        toolset=management,
        ids=[mcp.name],
        reason="The configured integration is needed.",
    )

    assert mcp.options.cls[options.Policy].value == options.Policies.FULL
    assert not mcp.activated
    assert mcp in manager.permitted
    assert mcp not in manager.agent

    result = asyncio.run(activation.run())

    assert result.new == [mcp.name]
    assert mcp.activated
    assert mcp in manager.agent
    assert mcp in manager.combined.toolsets
    assert management.toolsets == [SampleMCP]


def test_mcp_policy_values_other_than_disabled_allow_activation(mcp_server):
    server, _ = mcp_server

    class SampleMCP(ToolsetMCP):
        URL = server

    manager = make_acp_deps([Management, SampleMCP]).toolsets
    management = manager.all.name[Management.name]
    mcp = manager.all.name[SampleMCP.name]
    mcp.options.cls[options.Policy].current_value = options.Policies.REQUESTABLE
    context = RunContext(
        deps=SimpleNamespace(toolsets=manager),
        model=TestModel(),
        usage=RunUsage(),
    )
    approval = ApproveRequestables(
        ctx=context,
        toolset=management,
        ids=[mcp.name],
        reason="The configured integration is needed.",
    )
    activation = Activate(
        ctx=context,
        toolset=management,
        ids=[mcp.name],
        reason="The configured integration is needed.",
    )

    assert mcp in manager.permitted
    assert approval.requestables == []

    result = asyncio.run(activation.run())

    assert result.new == [mcp.name]
    assert mcp.activated


def test_approving_activation_only_changes_requestable_toolset_policies():
    deps = make_agent_deps([Files, Shell])
    files = deps.toolsets.all.name[Files.name]
    shell = deps.toolsets.all.name[Shell.name]
    context = RunContext(deps=deps, model=TestModel(), usage=RunUsage())
    approval = ApproveRequestables(
        ctx=context,
        toolset=files,
        ids=[Files.name, Shell.name],
        reason="Test activation approval",
    )

    asyncio.run(approval.after_approval())

    assert files.options.cls[options.Policy].value == options.Policies.AUTO
    assert shell.options.cls[options.Policy].value == options.Policies.APPROVAL


def test_activate_rejects_already_active_toolsets():
    parent = SimpleNamespace(
        settings=SimpleNamespace(),
        cwd_default=Path.cwd(),
        toolsets_classes=[Management, Files],
    )
    deps = ToolsetsManager(parent)
    management = deps.all.name[Management.name]
    files = deps.all.name[Files.name]
    files.activated = False
    context = RunContext(
        deps=SimpleNamespace(toolsets=deps), model=TestModel(), usage=RunUsage()
    )

    activation = Activate(
        ctx=context,
        toolset=management,
        ids=[Files.name],
        reason="Test activation",
    )
    result = asyncio.run(activation.run())

    assert isinstance(result, ActivationOutput)
    assert result.toolset_ids == [Files.name]
    assert result.activated == [Management.name]
    assert result.invalid_ids == []
    assert result.new == [Files.name]
    assert files.activated
    assert management.toolsets == [Files]

    tools = asyncio.run(management.get_tools(context))
    tool_def = tools[management.get_name(Activate)].tool_def
    with pytest.raises(ModelRetry):
        asyncio.run(
            management.validate(
                context,
                tool_def,
                {"ids": [Files.name], "reason": "Test repeated activation"},
            )
        )

    assert files.activated
    assert management.toolsets == [Files]


def test_activate_output_reports_unknown_ids_while_activating_known_ids():
    parent = SimpleNamespace(
        settings=SimpleNamespace(),
        cwd_default=Path.cwd(),
        toolsets_classes=[Management, Files],
    )
    deps = ToolsetsManager(parent)
    management = deps.all.name[Management.name]
    files = deps.all.name[Files.name]
    files.activated = False
    context = RunContext(
        deps=SimpleNamespace(toolsets=deps), model=TestModel(), usage=RunUsage()
    )
    tool = Activate(
        ctx=context,
        toolset=management,
        ids=[Files.name, "Missing"],
        reason="Test activation with an unknown ID",
    )

    result = asyncio.run(tool.run())

    assert files.activated
    assert isinstance(result, ActivationOutput)
    assert result.toolset_ids == [Files.name]
    assert result.invalid_ids == ["Missing"]
    assert result.activated == [Management.name]
    assert result.new == [Files.name]
