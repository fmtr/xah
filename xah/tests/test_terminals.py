import asyncio
import gc
import weakref

import pytest
from corio import Path
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from xah.tests.test_base import harness
from xah.toolsets.terminal.base import TerminalOutput
from xah.toolsets.shell.run import Run
from xah.toolsets.shell.toolset import Shell
from xah.toolsets.terminal.kill import Kill
from xah.toolsets.terminal.status import Status
from xah.toolsets.terminal.terminal import (
    TERMINAL_INLINE_OUTPUT_MAX_CHARS,
    TerminalStatus,
)
from xah.toolsets.terminal.toolset import Terminals


def context(runtime):
    model = TestModel(
        call_tools=[],
        custom_output_args={"block": False, "reasons": []},
    )
    runtime.deps.model = model
    return RunContext(
        deps=runtime.deps,
        model=model,
        usage=RunUsage(),
        tool_call_id="call-terminal",
    )


def test_short_terminal_does_not_notify_after_completion(tmp_path, monkeypatch):
    runtime = harness(Path(tmp_path))
    all_toolsets = runtime.deps.toolsets.all
    toolset = all_toolsets.cls[Shell]
    all_toolsets.name["Files"].activated = False
    all_toolsets.cls[Terminals].activated = False
    monkeypatch.setattr(Run, "QUICK_COMPLETION_TIMEOUT", 0.05)
    tool = Run(
        ctx=context(runtime),
        toolset=toolset,
        script="printf terminal-e2e",
        timeout=30,
    )

    result = asyncio.run(tool.run())
    terminal = runtime.deps.toolsets.all.cls[Terminals].terminals[0]

    assert isinstance(result, TerminalOutput)
    assert result.show_full_output
    assert result.displayed_output == "terminal-e2e"
    assert terminal.output_path.name not in result.agent
    assert terminal.tail() == "terminal-e2e"
    assert terminal.status is TerminalStatus.COMPLETED
    assert terminal.on_status is None
    assert not all_toolsets.name["Files"].activated
    assert not all_toolsets.cls[Terminals].activated


def test_terminal_output_at_inline_limit_stays_inline_through_toolset(tmp_path):
    runtime = harness(Path(tmp_path))
    toolset = runtime.deps.toolsets.all.cls[Shell]
    ctx = context(runtime)
    tool_name = toolset.get_name(Run)
    tools = asyncio.run(toolset.get_tools(ctx))
    result = asyncio.run(
        toolset.call_tool(
            tool_name,
            {"script": f"printf '%0{TERMINAL_INLINE_OUTPUT_MAX_CHARS}d' 0", "timeout": 30},
            ctx,
            tools[tool_name],
        )
    )

    terminal = runtime.deps.toolsets.all.cls[Terminals].terminals[0]

    assert "0" * TERMINAL_INLINE_OUTPUT_MAX_CHARS in result
    assert terminal.output_path.name not in result


def test_large_quick_terminal_externalizes_output_and_activates_tools(tmp_path):
    runtime = harness(Path(tmp_path))
    toolsets = runtime.deps.toolsets.all
    file_toolset = toolsets.name["Files"]
    terminal_toolset = toolsets.cls[Terminals]
    utils_toolset = toolsets.name["Utils"]
    file_toolset.activated = False
    terminal_toolset.activated = False
    utils_toolset.activated = False
    tool = Run(
        ctx=context(runtime),
        toolset=toolsets.cls[Shell],
        script=f"printf '%0{TERMINAL_INLINE_OUTPUT_MAX_CHARS + 1}d' 0",
        timeout=30,
    )

    result = asyncio.run(tool.run())
    terminal = terminal_toolset.terminals[0]

    captured_output = terminal.read_output(TERMINAL_INLINE_OUTPUT_MAX_CHARS + 1)

    assert len(captured_output) == TERMINAL_INLINE_OUTPUT_MAX_CHARS + 1
    assert isinstance(result, TerminalOutput)
    assert not result.show_full_output
    assert terminal.output_path.name in result.agent
    assert captured_output not in result.agent
    assert terminal.tail() in result.agent
    assert file_toolset.activated
    assert terminal_toolset.activated
    assert not utils_toolset.activated


@pytest.mark.asyncio
async def test_toolset_releases_tool_after_terminal_finishes(tmp_path, monkeypatch):
    runtime = harness(Path(tmp_path))
    toolset = runtime.deps.toolsets.all.cls[Shell]
    monkeypatch.setattr(Run, "QUICK_COMPLETION_TIMEOUT", 0.05)
    ctx = context(runtime)
    tools = await toolset.get_tools(ctx)
    task = asyncio.create_task(
        toolset.call_tool(
            toolset.get_name(Run),
            {"script": "sleep 1", "timeout": 30},
            ctx,
            tools[toolset.get_name(Run)],
        )
    )

    result = await task
    terminals = runtime.deps.toolsets.all.cls[Terminals].terminals
    terminal = terminals[0]
    tool_ref = weakref.ref(terminal.on_status.__self__)

    assert terminal.id in result
    assert not toolset.instances
    assert terminal.status.value == "running"
    assert tool_ref() is not None

    await terminal.process
    gc.collect()

    assert terminal.status.value == "completed"
    assert terminal.on_status is None
    assert tool_ref() is None


@pytest.mark.parametrize("tool_class", [Status, Kill])
def test_terminal_management_tools_report_unknown_ids_to_the_agent(tmp_path, tool_class):
    runtime = harness(Path(tmp_path))
    toolset = runtime.deps.toolsets.all.cls[Terminals]
    ctx = context(runtime)
    tool_name = toolset.get_name(tool_class)
    tools = asyncio.run(toolset.get_tools(ctx))

    with pytest.raises(ModelRetry):
        asyncio.run(
            toolset.validate(
                ctx,
                tools[tool_name].tool_def,
                {"terminal_id": "unknown"},
            )
        )

    assert not runtime.deps.toolsets.all.cls[Terminals].terminals


def test_terminal_kill_operates_on_a_background_shell_process(tmp_path, monkeypatch):
    runtime = harness(Path(tmp_path))
    monkeypatch.setattr(Run, "QUICK_COMPLETION_TIMEOUT", 0.05)
    toolset = runtime.deps.toolsets.all.cls[Shell]
    tool = Run(
        ctx=context(runtime),
        toolset=toolset,
        script="sleep 30",
        timeout=30,
    )

    result = asyncio.run(tool.run())
    terminal = runtime.deps.toolsets.all.cls[Terminals].terminals[0]
    kill = Kill(ctx=context(runtime), toolset=toolset, terminal_id=terminal.id)

    kill_result = asyncio.run(kill.run())

    assert terminal.id in result.agent
    assert kill_result.terminal.status is TerminalStatus.KILLED
