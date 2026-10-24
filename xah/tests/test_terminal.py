import asyncio
import os

from corio.shell.dsl import shell

import pytest

from xah.toolsets.base.toolset import Toolset
from xah.toolsets.terminal.base import TerminalTool
from xah.toolsets.terminal.output import Output
from xah.toolsets.terminal.status import Status
from xah.toolsets.terminal.terminal import Terminal, TerminalStatus


async def wait_for_process_exit(pid: int) -> None:
    for _ in range(25):
        if not os.path.exists(f"/proc/{pid}"):
            return
        await asyncio.sleep(0.02)

    pytest.fail(f"Process {pid} is still running")


def test_terminal_truncate_output_keeps_the_latest_8k_and_reports_lines():
    output = "".join(f"line {index}: {'x' * 100}\n" for index in range(250))
    omitted = output[:-TerminalTool.OUTPUT_MAX_CHARS]
    expected_lines = len(omitted.splitlines())

    truncated = TerminalTool.truncate_output(output)

    assert truncated.startswith(f"[{expected_lines} lines truncated]\n")
    assert truncated.endswith(output[-TerminalTool.OUTPUT_MAX_CHARS:])
    assert len(truncated.split("\n", 1)[1]) == TerminalTool.OUTPUT_MAX_CHARS


def test_terminal_truncate_output_preserves_short_output():
    output = "first\nsecond\n"

    assert TerminalTool.truncate_output(output) == output


def test_output_truncates_each_line_with_the_file_line_limit():
    output = "x" * (Output.MAX_LINE_LENGTH + 1)

    result = Output.format_output(output)

    assert len(result) <= Output.MAX_LINE_LENGTH
    assert result != output


def test_output_keeps_only_the_tail_when_total_output_is_too_long():
    output = "".join(f"line {index}\n" for index in range(Output.MAX_OUTPUT_LENGTH))

    result = Output.format_output(output)

    assert len(result) == Output.MAX_OUTPUT_LENGTH
    assert result == output[-Output.MAX_OUTPUT_LENGTH:]
    assert result.endswith(f"line {Output.MAX_OUTPUT_LENGTH - 1}\n")


def test_terminal_summary_includes_runtime_status_and_command():
    terminal = Terminal.model_construct(
        id="test",
        expression=shell.echo("012345678901234567890123"),
        cwd="/tmp",
        status="completed",
        exit_code=0,
        _started_at=10.0,
        _finished_at=12.5,
    )

    assert terminal.runtime == 2.5
    assert terminal.tail(20) == ""
    assert terminal.summary == (
        "Terminal `test` running `echo 012345678901234567890123` for 2.5 seconds.\n"
        "Status: `completed`; exit code: `0`."
    )


def test_output_notification_left_aligns_multiline_output(monkeypatch):
    messages = []
    terminal = Terminal.model_construct(
        id="test",
        expression=shell.echo("test"),
        cwd="/tmp",
        status="completed",
        exit_code=0,
        output="first\nsecond\nthird",
        _started_at=10.0,
        _finished_at=10.0,
    )
    monkeypatch.setattr(Toolset, "feedback", lambda ctx, message: messages.append(message))

    Output.notify(None, terminal)

    message = messages[0]
    assert message == (
        "Terminal produced output.\n"
        "Terminal `test` running `echo test` for 0 seconds.\n"
        "Status: `completed`; exit code: `0`.\n\n"
        "```\n"
        "first\n"
        "second\n"
        "third\n"
        "```\n\n"
        "Note: The above is the output tail only. Use the Output tool to inspect its full output."
    )
    assert all(not line.startswith(" ") for line in message.splitlines())


def test_output_notification_reports_no_new_output(monkeypatch):
    messages = []
    terminal = Terminal.model_construct(
        id="test",
        expression=shell.echo("test"),
        cwd="/tmp",
        status="completed",
        exit_code=0,
        output="",
        _started_at=10.0,
        _finished_at=10.0,
    )
    monkeypatch.setattr(Toolset, "feedback", lambda ctx, message: messages.append(message))

    Output.notify(None, terminal)

    assert "[No New Output]" in messages[0]


def test_status_notification_uses_shared_terminal_notification(monkeypatch):
    messages = []
    terminal = Terminal.model_construct(
        id="test",
        expression=shell.echo("test"),
        cwd="/tmp",
        status="completed",
        output="first\nsecond",
        exit_code=0,
        _started_at=10.0,
        _finished_at=10.0,
    )
    monkeypatch.setattr(Toolset, "feedback", lambda ctx, message: messages.append(message))

    Status.notify(None, terminal)

    message = messages[0]
    assert message == (
        "Terminal finished.\n"
        "Terminal `test` running `echo test` for 0 seconds.\n"
        "Status: `completed`; exit code: `0`.\n\n"
        "```\n"
        "first\n"
        "second\n"
        "```\n\n"
        "Note: The above is the output tail only. Use the Output tool to inspect its full output."
    )
    assert all(not line.startswith(" ") for line in message.splitlines())


@pytest.mark.asyncio
async def test_terminal_returns_incremental_output_and_completion_status():
    completed = []
    outputs = []
    terminal = Terminal.model_construct(
        id="test",
        expression=shell.sh("-c", "printf first; sleep 0.01; printf second"),
        timeout=2,
        cwd="/tmp",
        status=TerminalStatus.CREATED,
        output="",
        exit_code=None,
        on_complete=lambda terminal: completed.append(terminal.status),
        on_output=lambda terminal: outputs.append(terminal.output),
        _read_offset=0,
        _process_handle=None,
    )

    await terminal.start()
    await asyncio.sleep(0.05)

    assert await terminal.get() == "firstsecond"
    assert await terminal.get() == ""
    assert terminal.status == TerminalStatus.COMPLETED
    assert completed == [TerminalStatus.COMPLETED]
    assert outputs == []


@pytest.mark.asyncio
async def test_terminal_notifies_only_after_a_large_output_chunk():
    outputs = []
    terminal = Terminal.model_construct(
        id="test",
        expression=shell.head("-c", "8192", "/dev/zero"),
        timeout=2,
        cwd="/tmp",
        status=TerminalStatus.CREATED,
        output="",
        exit_code=None,
        on_output=lambda terminal: outputs.append(terminal.output),
        _read_offset=0,
        _process_handle=None,
    )

    await terminal.start()
    await terminal.process

    assert len(outputs) == 1
    assert len(outputs[0]) >= 2 * 1024
    assert await terminal.get()


@pytest.mark.asyncio
async def test_terminal_kill_stops_the_process():
    completed = []
    terminal = Terminal.model_construct(
        id="test",
        expression=shell.sleep("10"),
        timeout=2,
        cwd="/tmp",
        status=TerminalStatus.CREATED,
        output="",
        exit_code=None,
        on_complete=lambda terminal: completed.append(terminal.status),
        _read_offset=0,
        _process_handle=None,
    )

    await terminal.start()
    await asyncio.sleep(0)
    await terminal.kill()

    assert terminal.status == TerminalStatus.KILLED


@pytest.mark.asyncio
async def test_terminal_kill_terminates_the_process_group():
    completed = []
    terminal = Terminal.model_construct(
        id="test",
        expression=shell.sh("-c", "sleep 30 & echo $!; wait"),
        timeout=2,
        cwd="/tmp",
        status=TerminalStatus.CREATED,
        output="",
        exit_code=None,
        on_complete=lambda terminal: completed.append(terminal.status),
        _read_offset=0,
        _process_handle=None,
    )

    await terminal.start()
    await asyncio.sleep(0.05)
    child_pid = int((await terminal.get()).strip())

    await terminal.kill()
    await wait_for_process_exit(child_pid)


@pytest.mark.asyncio
async def test_terminal_kill_does_not_wait_for_inherited_pipes():
    terminal = Terminal.model_construct(
        id="test",
        expression=shell.sh("-c", "setsid sh -c 'sleep 30' & child=$!; echo $child; wait"),
        timeout=2,
        cwd="/tmp",
        status=TerminalStatus.CREATED,
        output="",
        exit_code=None,
        on_complete=None,
        _read_offset=0,
        _process_handle=None,
    )

    await terminal.start()
    await asyncio.sleep(0.05)
    child_pid = int((await terminal.get()).strip())
    kill_task = asyncio.create_task(terminal.kill())

    try:
        await asyncio.wait_for(asyncio.shield(kill_task), timeout=0.2)
    finally:
        os.kill(child_pid, 9)
        await kill_task

    assert terminal.status == TerminalStatus.KILLED


@pytest.mark.asyncio
async def test_terminal_timeout_terminates_the_process_group():
    completed = []
    terminal = Terminal.model_construct(
        id="test",
        expression=shell.sh("-c", "sleep 30 & echo $!; wait"),
        timeout=1,
        cwd="/tmp",
        status=TerminalStatus.CREATED,
        output="",
        exit_code=None,
        on_complete=lambda terminal: completed.append(terminal.status),
        _read_offset=0,
        _process_handle=None,
    )

    await terminal.start()
    await terminal.process
    child_pid = int((await terminal.get()).strip())

    assert terminal.status == TerminalStatus.TIMED_OUT
    await wait_for_process_exit(child_pid)
