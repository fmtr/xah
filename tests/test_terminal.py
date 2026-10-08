import asyncio
import os

import pytest

from xah.toolsets.terminal.terminal import Terminal, TerminalStatus



async def wait_for_process_exit(pid: int) -> None:
    for _ in range(25):
        if not os.path.exists(f"/proc/{pid}"):
            return
        await asyncio.sleep(0.02)

    pytest.fail(f"Process {pid} is still running")


@pytest.mark.asyncio
async def test_terminal_returns_incremental_output_and_completion_status():
    completed = []
    outputs = []
    terminal = Terminal.model_construct(
        id="test",
        command="printf first; sleep 0.01; printf second",
        shell="/bin/sh",
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
        command="head -c 8192 /dev/zero",
        shell="/bin/sh",
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
        command="sleep 10",
        shell="/bin/sh",
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
        command="sh -c 'sleep 30 & echo $!; wait'",
        shell="/bin/sh",
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
async def test_terminal_timeout_terminates_the_process_group():
    completed = []
    terminal = Terminal.model_construct(
        id="test",
        command="sh -c 'sleep 30 & echo $!; wait'",
        shell="/bin/sh",
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
