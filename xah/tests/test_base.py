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
from xah.harness.base import Harness, HarnessAgent
from xah.harness.deps import HarnessDeps
from xah.options.provider import ConfigOptionsProvider
from xah.paths import paths
from xah.options import base as options
from xah.toolsets.base.toolset import Toolset as ToolsetBase
from pydantic_acp import compose_projection_maps
from pydantic_acp.projection import FileEditToolCallContent
from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage
from xah.toolsets.fs.mkdir import Mkdir
from xah.toolsets.fs.path import PathPermissions
from xah.toolsets.fs.remove import Remove
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


def test_files_toolset_after_compress_uses_owner_specific_validator_state():
    files = Files(settings=SimpleNamespace(), cwd=Path.cwd())

    files.after_compress()

    mkdir_state = files.states[(Mkdir, PathPermissions)]
    remove_state = files.states[(Remove, PathPermissions)]
    assert mkdir_state is not remove_state


def test_harness_instructions_load_home_and_project_files(tmp_path):
    home = Path(tmp_path / "home")
    project = Path(tmp_path / "project")
    home.mkdirf()
    (project / ".agents").mkdirf()
    (home / ".agents").mkdirf()
    (home / ".agents" / "AGENTS.md").write_text("home instructions")
    (project / ".agents" / "AGENTS.md").write_text("project instructions")
    settings = SimpleNamespace(path=PathAgent(home=home, agents_dir=".agents"))
    harness = Harness(
        session=SimpleNamespace(cwd=project, session_id="test-session"),
        usage_reporters=UsageReporterRegistry(),
    )

    result = asyncio.run(harness.get_instructions(SimpleNamespace(deps=harness.deps)))

    assert "home instructions" in result
    assert "project instructions" in result
    assert f'You have read access to "{project.resolve()}".' in result
    assert f'You have write access to "{project.resolve()}".' in result


def test_harness_instructions_ignore_missing_files(tmp_path):
    home = Path(tmp_path / "skills")
    home.mkdirf()
    settings = SimpleNamespace(path=PathAgent(home=home, agents_dir=".agents"))
    harness = Harness(
        session=SimpleNamespace(cwd=Path(tmp_path), session_id="test-session"),
        usage_reporters=UsageReporterRegistry(),
    )

    assert harness.get_instructions_agent_md == []


def harness(cwd=None):
    session = SimpleNamespace(
        cwd=cwd or Path.cwd(),
        session_id="test-session",
    )
    runtime = Harness(
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
    toolset = harness_instance.deps.toolsets.name[Files.name]

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
    toolset = deps.toolsets.cls[Shell]
    model = TestModel(
        custom_output_args={
            "approval": True,
            "comments": "The command is appropriate.",
        }
    )
    ctx = RunContext(deps=deps, model=model, usage=RunUsage())
    tool_def = next(iter(toolset.tools.values())).tool_def

    assert toolset.options.cls[options.Policy].value == options.DISABLED
    toolset.options.cls[options.Policy].current_value = options.APPROVAL

    result = asyncio.run(toolset.validate(ctx, tool_def, {"source": "echo hello"}))

    assert result.approval
    assert result.messages == ["The command is appropriate."]


def test_terminal_run_appends_to_terminal_collection():
    deps = harness().deps
    toolset = deps.toolsets.cls[Terminals]
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
    shell = deps.toolsets.cls[Shell]

    assert shell.options.cls[options.Policy].value == options.DISABLED
    assert shell not in deps.active_toolsets

    shell.options.cls[options.Policy].current_value = options.FULL

    assert shell in deps.active_toolsets
    assert shell.wrapper in deps.approval_toolsets


def test_todo_policy_controls_visibility():
    deps = harness().deps
    todo = deps.toolsets.cls[Todo]

    todo.options.cls[options.Policy].current_value = options.DISABLED
    assert todo not in deps.active_toolsets

    todo.options.cls[options.Policy].current_value = options.FULL
    assert todo in deps.active_toolsets


def test_python_policy_has_one_value_representation():
    deps = harness().deps
    option = deps.toolsets.cls[Python].options.cls[options.Policy]

    assert option.value == options.APPROVAL
    assert [item.value for item in option.options] == [options.DISABLED, options.APPROVAL, options.AUTO, options.FULL]
    assert [item.name for item in option.options] == [options.DISABLED, options.APPROVAL, options.AUTO, options.FULL]


def test_select_enabled_can_be_overridden():
    class AlwaysEnabled(options.Select):
        @property
        def enabled(self):
            return True

    policy = options.Policy.from_value("Example", options.DISABLED)
    custom = AlwaysEnabled.from_values(
        values=[options.DISABLED],
        value=options.DISABLED,
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

    clone.toolsets.cls[Python].options.cls[options.Policy].current_value = options.DISABLED
    clone.options.name["PathWrite"].current_value = "/"

    assert deps.toolsets.cls[Python].options.cls[options.Policy].value == options.APPROVAL
    assert deps.options.name["PathWrite"].current_value == "."


def test_acp_provider_updates_dependency_option_state(tmp_path):
    source = SessionAgentSource(Harness, SETTINGS, usage_reporters=UsageReporterRegistry())
    session = SimpleNamespace(
        cwd=str(tmp_path),
        session_id="session",
        session_model_id=None,
        config_values={"PathRead": "."},
    )
    deps = asyncio.run(source.get_deps(session, None))
    provider = ConfigOptionsProvider(source)

    provider.set_config_option(session, None, "PathRead", "/")
    provider.set_config_option(session, None, "Python/Policy", options.DISABLED)
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
    assert deps.toolsets.cls[Python].options.cls[options.Policy].value == options.DISABLED


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

    class CustomHarness(Harness):
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
    assert HarnessDeps().toolsets == []


def test_harness_subclass_defines_its_toolset_catalogue():
    class Planner(Harness):
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
    assert planner.toolsets.cls[Todo].name == "Todo"
    assert planner.deps.toolsets is planner.toolsets


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

    class MultiOptionHarness(Harness):
        @classes
        def Toolsets(cls):
            return [Utils, MultiOptionToolset]

    selected = MultiOptionHarness(
        session=SimpleNamespace(cwd=Path.cwd(), session_id="test-session"),
        usage_reporters=UsageReporterRegistry(),
    )

    assert [option.id for option in selected.deps.options if option.category == "tools"] == [
        "Utils/Policy",
        "MultiOptionToolset/Policy",
        "MultiOptionToolset/ExtraOption",
    ]
    assert selected.toolsets[0] in selected.deps.active_toolsets

    selected.toolsets[0].options.cls[options.Policy].current_value = options.DISABLED

    assert selected.toolsets[0] not in selected.deps.active_toolsets
