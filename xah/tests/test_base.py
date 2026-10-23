from __future__ import annotations

import asyncio
import sys
from functools import cached_property
from types import SimpleNamespace
from unittest.mock import patch

from cached_classproperty import cached_classproperty
from corio import Path
from corio.iterator import ilist

from xah.class_collections import classes
from xah.server.acp.server import SessionAgentSource
from xah.server.acp.usage import UsageReporterRegistry
from xah.settings import PathAgent
from xah.harness.base import Harness, HarnessAcp
from xah.instructions.agent import Agent
from xah.harness.deps import HarnessDeps
from xah.options.provider import ConfigOptionsProvider
from xah.paths import paths
from xah.options import base as options
from xah.toolsets.base.tool import Messages
from xah.toolsets.base.toolset import Toolset as ToolsetBase, ToolsetInfo
from pydantic_acp import compose_projection_maps
from pydantic_acp.projection import FileEditToolCallContent
from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage
from xah.toolsets.fs.toolset import Files
from xah.toolsets.fs.write import Write
from xah.toolsets.python.toolset import Python
from xah.toolsets.shell.run import Run
from xah.toolsets.shell.toolset import Shell
from xah.toolsets.skills.toolset import Skills
from xah.toolsets.subagent.toolset import Subagent
from xah.toolsets.todo.toolset import Todo
from xah.toolsets.terminal.status import Status
from xah.toolsets.terminal.toolset import Terminals
from xah.toolsets.utils.toolset import Utils


SETTINGS = SimpleNamespace(port=8765, path=PathAgent())


def test_toolset_activation_and_info():
    toolset = ToolsetBase()

    assert toolset.activated
    assert toolset.info == ToolsetInfo(
        active=True,
        name=toolset.name,
        desc=toolset.description,
        protected=False,
        tools=[],
    )

    toolset.activated = False

    assert not toolset.activated


def test_harness_instructions_load_home_and_project_files(tmp_path):
    home = Path(tmp_path / "home")
    project = Path(tmp_path / "project")
    home.mkdirf()
    (project / ".agents").mkdirf()
    (home / ".agents").mkdirf()
    (home / ".agents" / "AGENTS.md").write_text("home instructions")
    (project / ".agents" / "AGENTS.md").write_text("project instructions")
    settings = SimpleNamespace(path=PathAgent(home=home, agents_dir=".agents"))
    harness = HarnessAcp(
        session=SimpleNamespace(cwd=project, session_id="test-session"),
        usage_reporters=UsageReporterRegistry(),
    )

    result = asyncio.run(harness.get_instructions(SimpleNamespace(deps=harness.deps)))

    assert "home instructions" not in result
    assert "project instructions" in result
    assert f'You have read access to "{project.resolve()}".' in result
    assert f'You have write access to "{project.resolve()}".' in result


def test_harness_instructions_ignore_missing_files(tmp_path):
    home = Path(tmp_path / "skills")
    home.mkdirf()
    settings = SimpleNamespace(path=PathAgent(home=home, agents_dir=".agents"))
    harness = HarnessAcp(
        session=SimpleNamespace(cwd=Path(tmp_path), session_id="test-session"),
        usage_reporters=UsageReporterRegistry(),
    )

    context = SimpleNamespace(deps=harness.deps)
    assert asyncio.run(Agent(ctx=context, harness_type=type(harness)).run()) == []


def harness(cwd=None):
    session = SimpleNamespace(
        cwd=cwd or Path.cwd(),
        session_id="test-session",
    )
    runtime = HarnessAcp(
        session=session,
        usage_reporters=UsageReporterRegistry(),
    )
    with patch.object(sys, "argv", [sys.argv[0]]):
        runtime.settings
    return runtime


def test_harness_ignores_non_progress_tools_in_stuck_loop_detection():
    assert harness().stuck_loop_detection.ignore_tools == {"Files-Edit", "Utils-Sleep"}


def test_similarity_validator_has_shared_thresholds():
    from xah.toolsets.fs.similarity import SimilarityValidator

    assert SimilarityValidator.SIMILARITY_MIN_LENGTH == 250
    assert SimilarityValidator.SIMILARITY_MIN_PERCENT == 80


def test_toolset_projections_are_owned_by_toolsets():
    harness_instance = harness()
    toolset = harness_instance.deps.toolsets.all.name[Files.name]

    write_projections = [
        projection
        for projection in toolset.projections
        if toolset.tool_name(Write) in projection.write_tool_names
    ]

    assert len(write_projections) == 1


def test_harness_builds_projections_without_deps():
    harness_instance = harness()

    projections = harness_instance.projections

    assert projections
    assert "deps" not in harness_instance.__dict__


def test_files_write_projection_is_a_diff_without_default_tool_names():
    harness_instance = harness()
    write_projection = next(
        projection
        for projection in harness_instance.projections
        if "Files-Write" in projection.write_tool_names
    )

    assert write_projection.read_tool_names == frozenset()
    assert write_projection.edit_tool_names == frozenset()
    assert write_projection.search_tool_names == frozenset()
    assert harness_instance.adapter_config.tool_classifier.classify("Files-Write") == "edit"

    projection = compose_projection_maps(harness_instance.projections).project_start(
        "Files-Write",
        raw_input={"path": "bad.py", "content": "bad"},
    )

    assert projection.content == [
        FileEditToolCallContent(
            type="diff",
            path="bad.py",
            old_text="",
            new_text="bad",
        )
    ]


def test_shell_validation_uses_agent_output():
    deps = harness().deps
    toolset = deps.toolsets.all.cls[Shell]
    model = TestModel(
        call_tools=[],
        custom_output_args={
            "block": False,
            "reasons": [],
        }
    )
    deps.model = model
    ctx = RunContext(deps=deps, model=model, usage=RunUsage())
    tool_def = next(iter(toolset.tools.values())).tool_def

    assert toolset.options.cls[options.Policy].value == options.Policies.DISABLED
    toolset.options.cls[options.Policy].current_value = options.Policies.APPROVAL

    result = asyncio.run(toolset.validate(ctx, tool_def, {"source": "echo hello"}))

    assert result.approval
    assert result.messages == Messages()


def test_terminal_run_appends_to_terminal_collection():
    deps = harness().deps
    toolset = deps.toolsets.all.cls[Terminals]
    terminals = toolset.terminals
    ctx = RunContext(deps=deps, model=TestModel(), usage=RunUsage())
    tool = Run(ctx=ctx, toolset=toolset, source="printf hello")

    result = asyncio.run(tool.run())

    assert result == "hello"
    assert tool.terminals is terminals
    assert terminals[0].output == "hello"

    management_tool = Status(ctx=ctx, toolset=toolset, terminal_id=terminals[0].id)

    assert management_tool.terminals is terminals
    assert management_tool.terminal is terminals[0]


def test_policy_value_controls_toolset_visibility():
    deps = harness().deps
    shell = deps.toolsets.all.cls[Shell]

    assert shell.options.cls[options.Policy].value == options.Policies.DISABLED
    assert shell not in deps.toolsets.permitted

    shell.options.cls[options.Policy].current_value = options.Policies.FULL

    assert shell in deps.toolsets.permitted
    assert shell.wrapper not in deps.toolsets.wrapped


def test_todo_policy_controls_visibility():
    deps = harness().deps
    todo = deps.toolsets.all.cls[Todo]

    todo.options.cls[options.Policy].current_value = options.Policies.DISABLED
    assert todo not in deps.toolsets.permitted

    todo.options.cls[options.Policy].current_value = options.Policies.FULL
    assert todo in deps.toolsets.permitted


def test_python_policy_has_one_value_representation():
    deps = harness().deps
    option = deps.toolsets.all.cls[Python].options.cls[options.Policy]

    assert option.value == options.Policies.APPROVAL
    assert [item.value for item in option.options] == [policy.value for policy in options.Policies]
    assert [item.name for item in option.options] == [policy.value for policy in options.Policies]


def test_select_enabled_can_be_overridden():
    class AlwaysEnabled(options.Select):
        @property
        def enabled(self):
            return True

    policy = options.Policy.from_value("Example", options.Policies.DISABLED)
    custom = AlwaysEnabled.from_values(
        values=[options.Policies.DISABLED],
        value=options.Policies.DISABLED,
        description=None,
        category="test",
    )

    assert not policy.enabled
    assert custom.enabled


def test_session_options_include_paths(tmp_path):
    deps = harness(Path(tmp_path)).deps

    assert deps.options.name["PathCwd"].value == Path(tmp_path).resolve()
    assert deps.options.name["PathRead"].value == Path(tmp_path).resolve()
    assert deps.options.name["PathWrite"].value == Path(tmp_path).resolve()
    assert paths.dev_repo.as_posix() in {
        option.value for option in deps.options.name["PathRead"].options
    }


def test_subagent_clone_has_independent_options(tmp_path):
    deps = harness(Path(tmp_path)).deps
    clone = deps.clone_for_subagent()

    clone.toolsets.all.cls[Python].options.cls[options.Policy].current_value = options.Policies.DISABLED
    clone.options.name["PathWrite"].current_value = "/"

    assert deps.toolsets.all.cls[Python].options.cls[options.Policy].value == options.Policies.APPROVAL
    assert deps.options.name["PathWrite"].current_value == "."


def test_deps_update_config_sends_current_visible_options():
    class Client:
        def __init__(self):
            self.updates = []

        async def session_update(self, **kwargs):
            self.updates.append(kwargs)

    runtime = harness()
    client = Client()
    runtime.session.client = client

    asyncio.run(runtime.deps.update_config())

    assert len(client.updates) == 1
    update = client.updates[0]
    assert update["session_id"] == runtime.session.session_id
    assert update["update"].session_update == "config_option_update"
    assert update["update"].config_options == [
        option for option in runtime.deps.options if option.VISIBLE
    ]


def test_acp_provider_updates_dependency_option_state(tmp_path):
    source = SessionAgentSource(HarnessAcp, SETTINGS, usage_reporters=UsageReporterRegistry())
    session = SimpleNamespace(
        cwd=str(tmp_path),
        session_id="session",
        session_model_id=None,
        config_values={"PathRead": "."},
    )
    deps = asyncio.run(source.get_deps(session, None))
    provider = ConfigOptionsProvider(source)

    provider.set_config_option(session, None, "PathRead", "/")
    provider.set_config_option(session, None, "Python/Policy", options.Policies.DISABLED)
    same_deps = asyncio.run(source.get_deps(session, None))

    assert [option.id for option in provider.get_config_options(session, None)] == [
        option.id for option in deps.options if option.VISIBLE
    ]
    assert "PathCwd" in deps.options.name
    assert "PathCwd" not in {
        option.id for option in provider.get_config_options(session, None)
    }
    assert same_deps is deps
    assert source.session_id[session.session_id].deps is deps
    assert deps.options.name["PathRead"].current_value == "/"
    assert deps.toolsets.all.cls[Python].options.cls[options.Policy].value == options.Policies.DISABLED


def test_harness_creates_fresh_agents():
    first = harness().agent
    second = harness().agent

    assert first is not second
    assert first.description == "Root/orchestrator agent"
    assert second.description == "Root/orchestrator agent"


def test_harness_subclass_adds_capabilities_after_thinking():
    class CustomCapability(AbstractCapability):
        pass

    capability = CustomCapability()

    class CustomHarness(HarnessAcp):
        @cached_property
        def capabilities(self):
            return [capability]

    selected = CustomHarness(
        session=SimpleNamespace(cwd=Path.cwd(), session_id="test-session"),
        usage_reporters=UsageReporterRegistry(),
    )

    assert selected.capabilities == [capability]
    assert selected.agent_capabilities[:3] == [
        selected.thinking,
        capability,
        selected.stuck_loop_detection,
    ]


def test_harness_deps_are_generic():
    assert HarnessDeps().toolsets.all == []


def test_harness_subclass_defines_its_toolset_catalogue():
    class Planner(HarnessAcp):
        title = "Planner"

        @classes
        def Toolsets(cls):
            return [Todo, Utils]

    session = SimpleNamespace(cwd=Path.cwd(), session_id="test-session")
    planner = Planner(
        session=session,
        usage_reporters=UsageReporterRegistry(),
    )

    assert planner.name == "Planner"
    assert planner.title == "Planner"
    assert planner.Toolsets == [Todo, Utils]
    assert planner.Toolsets == [Todo, Utils]
    assert planner.deps.toolsets.all.cls[Todo].name == "Todo"
    assert planner.deps.toolsets.all is planner.deps.toolsets.all


def test_harness_flattens_toolset_option_lists():
    class ExtraOption(options.Select):
        pass

    class MultiOptionToolset(ToolsetBase):
        """Tools with an additional configuration option."""

        @cached_property
        def options(self):
            return ilist([
                options.Policy.from_value(self.name),
                ExtraOption.from_values(
                    name=self.name,
                    values=["one", "two"],
                    value="one",
                    description="Additional setting.",
                    category="tools",
                ),
            ])

    class MultiOptionHarness(HarnessAcp):
        @classes
        def Toolsets(cls):
            return [Utils, MultiOptionToolset]

    selected = MultiOptionHarness(
        session=SimpleNamespace(cwd=Path.cwd(), session_id="test-session"),
        usage_reporters=UsageReporterRegistry(),
    )

    assert [option.id for option in selected.deps.options if option.category == "tools"] == [
        "MultiOptionToolset/ExtraOption",
        "MultiOptionToolset/Policy",
        "Utils/Policy",
    ]
    assert selected.deps.toolsets.all[0] in selected.deps.toolsets.permitted

    selected.deps.toolsets.all[0].options.cls[options.Policy].current_value = options.Policies.DISABLED

    assert selected.deps.toolsets.all[0] not in selected.deps.toolsets.permitted
