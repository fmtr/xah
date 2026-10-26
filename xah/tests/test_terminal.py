import asyncio
import os
from types import SimpleNamespace

import pytest
from pydantic import PrivateAttr
from corio import Path
from corio.shell.dsl import shell

from xah.toolsets.base.tool import Tool
from xah.toolsets.shell.run import Run
from xah.toolsets.terminal.terminal import Terminal, TerminalStatus


class RecordingTool(Tool):
    _notifications: int = PrivateAttr(default=0)

    def notify(self):
        self._notifications += 1
        return "notified"


def test_terminal_output_path_treats_absolute_executable_as_a_filename(tmp_path):
    harness_cwd = Path(tmp_path / "project")
    home = Path(tmp_path / ".xah")
    deps = SimpleNamespace(
        cwd_default=harness_cwd,
        settings=SimpleNamespace(path=SimpleNamespace(home=home)),
    )
    tool = Run.model_construct(
        ctx=SimpleNamespace(deps=deps, tool_call_id="absolute-shell"),
    )
    tool.__dict__["expression"] = SimpleNamespace(name="/system/bin/bash")

    assert tool.output_path.parent == harness_cwd / home.name / "terminals"
    assert tool.output_path.name.startswith("bash-")


@pytest.mark.asyncio
async def test_terminal_writes_output_to_file(tmp_path):
    tool = RecordingTool.model_construct()
    terminal = Terminal(
        id="test",
        on_status=tool.notify,
        expression=shell.sh("-c", "printf first; printf second >&2"),
        timeout=2,
        cwd="/tmp",
        output_path=Path(str(tmp_path / "terminal.log")),
    )

    await terminal.start()
    await terminal.process

    assert terminal.status == TerminalStatus.COMPLETED
    assert tool._notifications == 1
    assert terminal.on_status is None
    assert terminal.output_size == len("firstsecond")
    assert terminal.output_path.read_text() == "firstsecond"
    assert await terminal.get() == "firstsecond"
    assert await terminal.get() == ""


@pytest.mark.asyncio
async def test_terminal_summary_tracks_lifecycle(tmp_path):
    terminal = Terminal(
        id="test",
        on_status=lambda: "notified",
        expression=shell.sleep("0.1"),
        timeout=2,
        cwd="/tmp",
        output_path=Path(str(tmp_path / "terminal.log")),
    )

    await terminal.start()
    assert "running" in terminal.summary
    await terminal.process

    assert "completed" in terminal.summary
    assert terminal.on_status is None


@pytest.mark.asyncio
async def test_terminal_tail_reads_from_output_file(tmp_path):
    tool = RecordingTool.model_construct()
    terminal = Terminal(
        id="test",
        on_status=tool.notify,
        expression=shell.echo("0123456789"),
        timeout=2,
        cwd="/tmp",
        output_path=Path(str(tmp_path / "terminal.log")),
    )

    await terminal.start()
    await terminal.process

    assert terminal.tail(5) == "6789"


@pytest.mark.asyncio
async def test_terminal_kill_stops_the_process(tmp_path):
    tool = RecordingTool.model_construct()
    terminal = Terminal(
        id="test",
        on_status=tool.notify,
        expression=shell.sleep("10"),
        timeout=2,
        cwd="/tmp",
        output_path=Path(str(tmp_path / "terminal.log")),
    )

    await terminal.start()
    await asyncio.sleep(0)
    await terminal.kill()

    assert terminal.status == TerminalStatus.KILLED


@pytest.mark.asyncio
async def test_terminal_kill_terminates_the_process_group(tmp_path):
    tool = RecordingTool.model_construct()
    terminal = Terminal(
        id="test",
        on_status=tool.notify,
        expression=shell.sh("-c", "sleep 30 & echo $!; wait"),
        timeout=2,
        cwd="/tmp",
        output_path=Path(str(tmp_path / "terminal.log")),
    )

    await terminal.start()
    await asyncio.sleep(0.05)
    child_pid = int((await terminal.get()).strip())

    await terminal.kill()
    for _ in range(25):
        if not os.path.exists(f"/proc/{child_pid}"):
            break
        await asyncio.sleep(0.02)
    else:
        pytest.fail(f"Process {child_pid} is still running")


@pytest.mark.asyncio
async def test_terminal_timeout_terminates_the_process_group(tmp_path):
    tool = RecordingTool.model_construct()
    terminal = Terminal(
        id="test",
        on_status=tool.notify,
        expression=shell.sh("-c", "sleep 30 & echo $!; wait"),
        timeout=1,
        cwd="/tmp",
        output_path=Path(str(tmp_path / "terminal.log")),
    )

    await terminal.start()
    await terminal.process
    child_pid = int((await terminal.get()).strip())

    assert terminal.status == TerminalStatus.TIMED_OUT
    for _ in range(25):
        if not os.path.exists(f"/proc/{child_pid}"):
            break
        await asyncio.sleep(0.02)
    else:
        pytest.fail(f"Process {child_pid} is still running")
