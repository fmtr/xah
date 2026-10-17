import asyncio
from types import SimpleNamespace

from corio import Path
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from xah.harness.base import Harness, HarnessAcp, HarnessBase
from corio.iterator import ilist

from xah.harness.deps import HarnessAgentDeps, HarnessDeps
from xah.options import base as options
from xah.toolsets.base.toolset import Toolset
from xah.toolsets.fs.toolset import Files
from xah.toolsets.shell.toolset import Shell
from xah.toolsets.todo.toolset import Todo
from xah.toolsets.management.activate import Activate
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


def test_acp_permitted_toolsets_follow_policy_state():
    deps = make_acp_deps([Files, Shell])
    files = deps.toolsets.all.cls[Files]
    shell = deps.toolsets.all.cls[Shell]

    assert deps.toolsets.permitted == ilist([files])
    assert deps.toolsets.wrapped == [files.wrapper]

    shell.options.cls[options.Policy].current_value = options.FULL

    assert deps.toolsets.permitted == ilist([files, shell])
    assert {wrapped.wrapped for wrapped in deps.toolsets.wrapped} == {files, shell}

    files.options.cls[options.Policy].current_value = options.DISABLED

    assert deps.toolsets.permitted == ilist([shell])
    assert deps.toolsets.wrapped == [shell.wrapper]


def test_acp_toolset_options_include_configured_toolsets_even_when_disabled():
    deps = make_acp_deps([Todo, Shell])
    shell = deps.toolsets.all.cls[Shell]

    shell.options.cls[options.Policy].current_value = options.DISABLED

    assert "Todo/Policy" in deps.options.name
    assert "Shell/Policy" in deps.options.name
    assert shell not in deps.toolsets.permitted


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

    assert manager.permitted == ilist([manager.all.name[Files.name]])
    assert manager.agent == ilist([manager.all.name[Files.name]])

    shell.options.cls[options.Policy].current_value = options.FULL
    assert manager.permitted == manager.all
    assert {type(toolset) for toolset in manager.agent} == {Files, Shell}

    manager.all.name[Files.name].activated = False
    assert manager.agent == ilist([shell])


def test_activate_reports_management_toolset_cannot_be_disabled():
    management = Management(settings=SimpleNamespace(), cwd=Path.cwd())
    files = Files(settings=SimpleNamespace(), cwd=Path.cwd())
    deps = SimpleNamespace(toolsets=SimpleNamespace(permitted=ilist([management, files])))
    context = RunContext(deps=deps, model=TestModel(), usage=RunUsage())
    tool = Activate(
        ctx=context,
        toolset=management,
        ids=[Management.name, Files.name],
        activate=False,
    )

    asyncio.run(tool.run())

    assert management.activated
    assert not files.activated
    assert tool.validation.messages == [
        "The Management toolset cannot be deactivated."
    ]
