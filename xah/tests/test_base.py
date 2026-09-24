from __future__ import annotations

import asyncio
from functools import cached_property
from types import SimpleNamespace

from cached_classproperty import cached_classproperty
from corio import Path
from corio.iterator import ilist

from xah.acp.server import SessionAgentSource
from xah.settings import PathAgent
from xah.harness.base import HarnessBase
from xah.harness.deps import HarnessDeps
from xah.options.provider import ConfigOptionsProvider
from xah.paths import paths
from xah.options import base as options
from xah.toolsets.base.approval import ApprovalMetadata
from xah.toolsets.base.toolset import Base as ToolsetBase
from pydantic_acp import compose_projection_maps
from pydantic_acp.projection import FileEditToolCallContent
from pydantic_ai import RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.usage import RunUsage
from xah.toolsets.fs.toolset import Files
from xah.toolsets.python.toolset import Python
from xah.toolsets.shell.toolset import Shell
from xah.toolsets.skills.toolset import Skills
from xah.toolsets.subagent.toolset import Subagent
from xah.toolsets.todo.toolset import Todo


SETTINGS = SimpleNamespace(port=8765, path=PathAgent())


def test_harness_instructions_load_home_and_project_files(tmp_path):
    home = Path(tmp_path / "home")
    project = Path(tmp_path / "project")
    home.mkdirf()
    (project / ".agents").mkdirf()
    (home / ".agents").mkdirf()
    (home / ".agents" / "AGENTS.md").write_text("home instructions")
    (project / ".agents" / "AGENTS.md").write_text("project instructions")
    settings = SimpleNamespace(path=PathAgent(home=home, agents_dir=".agents"))
    harness = HarnessBase(
        settings,
        session=SimpleNamespace(cwd=project),
    )

    result = asyncio.run(harness.dynamic_instructions(SimpleNamespace(deps=harness.deps)))

    assert "home instructions" in result
    assert "project instructions" in result
    assert f'You have read access to "{project.resolve()}".' in result
    assert f'You have write access to "{project.resolve()}".' in result


def test_harness_instructions_ignore_missing_files(tmp_path):
    home = Path(tmp_path / "skills")
    home.mkdirf()
    settings = SimpleNamespace(path=PathAgent(home=home, agents_dir=".agents"))
    harness = HarnessBase(
        settings,
        session=SimpleNamespace(cwd=Path(tmp_path)),
    )

    assert harness.agents_md_instructions == []


def harness(cwd=None):
    session = SimpleNamespace(cwd=cwd or Path.cwd())
    return HarnessBase(SETTINGS, session=session)


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


def test_shell_requires_approval_when_policy_is_approval():
    deps = harness().deps
    toolset = deps.toolsets.cls[Shell]
    ctx = RunContext(deps=deps, model=None, usage=RunUsage())
    tool_def = next(iter(toolset.tools.values())).tool_def

    assert toolset.options.cls[options.Policy].value == options.DISABLED
    toolset.options.cls[options.Policy].current_value = options.APPROVAL

    assert asyncio.run(toolset.validate(ctx, tool_def, {"shell": "echo hello"})) == ApprovalMetadata(
        msgs=["Approval required"],
    )


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
    assert [item.value for item in option.options] == [options.DISABLED, options.APPROVAL, options.FULL]
    assert [item.name for item in option.options] == [options.DISABLED, options.APPROVAL, options.FULL]


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
    source = SessionAgentSource(HarnessBase, SETTINGS)
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
        option.id for option in deps.options
    ]
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

    class CustomHarness(HarnessBase):
        @cached_property
        def capabilities(self):
            return [capability]

    selected = CustomHarness(
        SETTINGS,
        session=SimpleNamespace(cwd=Path.cwd()),
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
    class Planner(HarnessBase):
        title = "Planner"

        @cached_classproperty
        def TOOLSETS(cls):
            return {
                Files: False,
                Shell: False,
                Python: False,
                Skills: False,
                Subagent: False,
            }

    session = SimpleNamespace(cwd=Path.cwd())
    planner = Planner(SETTINGS, session=session)

    assert planner.name == "Planner"
    assert planner.title == "Planner"
    assert planner.TOOLSETS == {
        Files: False,
        Shell: False,
        Python: False,
        Skills: False,
        Subagent: False,
    }
    assert planner.toolset_classes == [Todo]
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

    class MultiOptionHarness(HarnessBase):
        @cached_classproperty
        def TOOLSETS(cls):
            return {
                Files: False,
                Shell: False,
                Python: False,
                Skills: False,
                Subagent: False,
                Todo: False,
                MultiOptionToolset: True,
            }

    selected = MultiOptionHarness(
        SETTINGS,
        session=SimpleNamespace(cwd=Path.cwd()),
    )

    assert [option.id for option in selected.options_toolsets] == [
        "MultiOptionToolset/Policy",
        "MultiOptionToolset/ExtraOption",
    ]
    assert selected.toolsets[0] in selected.deps.active_toolsets

    selected.toolsets[0].options.cls[options.Policy].current_value = options.DISABLED

    assert selected.toolsets[0] not in selected.deps.active_toolsets
