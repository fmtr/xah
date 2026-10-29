import asyncio
import os
import signal
import time
from collections.abc import Callable
from enum import StrEnum, auto
from typing import ClassVar

import humanize
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from corio import Path, dm, strings
from corio.function import cp
from corio.shell.dsl import Expression



class TerminalStatus(StrEnum):
    CREATED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    TIMED_OUT = auto()
    KILLED = auto()
    FAILED = auto()


class Terminal(dm.Base):
    """A background process whose output is written to a file."""

    READ_CHUNK_SIZE: ClassVar[int] = 4096
    TAIL_LENGTH: ClassVar[int] = 256
    SUMMARY_MASK: ClassVar[str] = strings.trim("""
        Terminal `{id}` running `{command}` for {runtime}.
        Last output: {last_output} ago.
        Status: `{status}`; exit code: `{exit_code}`.        
    """)

    id: str = Field(description="Identifier used by the terminal management tools.")
    expression: Expression = Field(description="DSL expression being run.", exclude=True)
    timeout: int | None = Field(default=None, description="Maximum execution time in seconds; None means no timeout.")
    cwd: str = Field(description="Working directory used by the command.")
    output_path: Path = Field(description="File receiving combined stdout and stderr output.")
    on_status: SkipJsonSchema[Callable[[], str] | None] = Field(default=None, exclude=True)
    status: TerminalStatus = TerminalStatus.CREATED
    output_size: int = 0
    exit_code: int | None = None

    _started_at: float = 0
    _last_output_at: float = 0
    _finished_at: float = 0
    _process_handle: asyncio.subprocess.Process | None = None

    @property
    def runtime(self) -> float:
        finished_at = self._finished_at or time.monotonic()
        return finished_at - self._started_at

    @property
    def output_idle(self) -> float:
        return time.monotonic() - self._last_output_at

    def tail(self, length: int | None = None) -> str:
        if length is None:
            length = self.TAIL_LENGTH
        with self.output_path.open("rb") as file:
            file.seek(max(self.output_size - length, 0))
            output = file.read(length).decode(errors="replace")
        return output.strip()

    @property
    def summary(self) -> str:
        command = strings.truncate_mid(str(self.expression), length=60)
        return strings.Mask(self.SUMMARY_MASK).format(
            id=self.id,
            command=command,
            cwd=self.cwd,
            runtime=humanize.precisedelta(self.runtime, format="%0.1f"),
            status=self.status,
            exit_code=self.exit_code,
            last_output=humanize.precisedelta(self.output_idle, format="%0.1f"),
        )

    @cp
    def process(self) -> asyncio.Task:
        self._started_at = time.monotonic()
        self._last_output_at = self._started_at
        return asyncio.create_task(self._run())

    def set(self, status: TerminalStatus) -> None:
        if self.status == status:
            return
        self.status = status
        if self.on_status:
            self.on_status()

    async def start(self) -> TerminalStatus:
        self.status = TerminalStatus.RUNNING
        self.process
        return self.status

    async def _read(self, stream: asyncio.StreamReader, output_file) -> None:
        while chunk := await stream.read(self.READ_CHUNK_SIZE):
            output_file.write(chunk)
            output_file.flush()
            self.output_size += len(chunk)
            self._last_output_at = time.monotonic()

    async def _run(self) -> None:
        readers = []
        terminated = False
        output_file = self.output_path.open("ab")
        try:
            process = await asyncio.create_subprocess_exec(
                self.expression.name,
                *self.expression.tokens(args_only=True),
                cwd=self.cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
            self._process_handle = process
            readers = [
                asyncio.create_task(self._read(process.stdout, output_file)),
                asyncio.create_task(self._read(process.stderr, output_file)),
            ]
            try:
                await asyncio.wait_for(process.wait(), timeout=self.timeout)
            except TimeoutError:
                self.set(TerminalStatus.TIMED_OUT)
            except asyncio.CancelledError:
                self.set(TerminalStatus.KILLED)
                raise
            finally:
                if self.status in (TerminalStatus.TIMED_OUT, TerminalStatus.KILLED):
                    for reader in readers:
                        reader.cancel()
                    await self._terminate(process)
                    terminated = True
                await asyncio.gather(*readers, return_exceptions=True)

            self.exit_code = process.returncode
            if self.status == TerminalStatus.RUNNING:
                status = TerminalStatus.COMPLETED if process.returncode == 0 else TerminalStatus.FAILED
                self.set(status)
        except asyncio.CancelledError:
            if self._process_handle and not terminated:
                await self._terminate(self._process_handle)
            self.set(TerminalStatus.KILLED)
            raise
        except OSError as error:
            self.set(TerminalStatus.FAILED)
            error_text = str(error).encode()
            output_file.write(error_text)
            output_file.flush()
            self.output_size += len(error_text)
        finally:
            output_file.close()
            self._finished_at = time.monotonic()
            self._process_handle = None
            self.on_status = None

    async def _terminate(self, process: asyncio.subprocess.Process) -> None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return

    async def kill(self) -> TerminalStatus:
        if self.process.done():
            return self.status
        self.process.cancel()
        await asyncio.gather(self.process, return_exceptions=True)
        return self.status

