import asyncio
import gc
import weakref

import pytest
from corio import Path
from pydantic_ai import RunContext
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from xah.tests.test_base import harness
from xah.toolsets.shell.run import Run
from xah.toolsets.shell.toolset import Shell
from xah.toolsets.terminal.kill import Kill
from xah.toolsets.terminal.status import Status
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
    toolset = runtime.deps.toolsets.all.cls[Shell]
    monkeypatch.setattr(Run, "QUICK_COMPLETION_TIMEOUT", 0.05)
    tool = Run(
        ctx=context(runtime),
        toolset=toolset,
        script="printf terminal-e2e",
        timeout=30,
    )

    result = asyncio.run(tool.run())
    terminal = runtime.deps.toolsets.all.cls[Terminals].terminals[0]

    assert result == "terminal-e2e"
    assert terminal.on_status is None


@pytest.mark.asyncio
async def test_toolset_releases_tool_after_terminal_finishes(tmp_path, monkeypatch):
    runtime = harness(Path(tmp_path))
    toolset = runtime.deps.toolsets.all.cls[Shell]
    monkeypatch.setattr(Run, "QUICK_COMPLETION_TIMEOUT", 0.05)
    ctx = context(runtime)
    tools = await toolset.get_tools(ctx)
    task = asyncio.create_task(
        toolset.call_tool(
            toolset.tool_name(Run),
            {"script": "sleep 1", "timeout": 30},
            ctx,
            tools[toolset.tool_name(Run)],
        )
    )

    result = await task
    terminals = runtime.deps.toolsets.all.cls[Terminals].terminals
    terminal = terminals[0]
    tool_ref = weakref.ref(terminal.on_status.__self__)

    assert result.startswith(f"Terminal `{terminal.id}`")
    assert not toolset.instances
    assert terminal.status.value == "running"
    assert tool_ref() is not None

    await terminal.process
    gc.collect()

    assert terminal.status.value == "completed"
    assert terminal.on_status is None
    assert tool_ref() is None


def test_terminal_status_rejects_an_unknown_terminal_id(tmp_path):
    runtime = harness(Path(tmp_path))
    toolset = runtime.deps.toolsets.all.cls[Terminals]
    status = Status(ctx=context(runtime), toolset=toolset, terminal_id="unknown")

    asyncio.run(status.validate())

    assert status.validation.messages.errors == ["Terminal with ID 'unknown' not found"]
    assert status.validation.abort


def test_terminal_kill_operates_on_a_background_shell_process(tmp_path):
    runtime = harness(Path(tmp_path))
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

    assert result.startswith(f"Terminal `{terminal.id}`")
    assert kill_result == f"Terminal `{terminal.id}` has status `killed`."
