import asyncio
import os
import signal
import time
from collections.abc import Callable
from enum import StrEnum, auto
from typing import ClassVar
from uuid import uuid4

import humanize
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from corio import dm, strings
from corio.function import cp
from corio.hash import get_hash_readable
from corio.shell.dsl import Expression


class TerminalStatus(StrEnum):
    CREATED = auto()
    RUNNING = auto()
    COMPLETED = auto()
    TIMED_OUT = auto()
    KILLED = auto()
    FAILED = auto()


class Terminal(dm.Base):
    """A background process whose output can be read incrementally."""

    READ_CHUNK_SIZE: ClassVar[int] = 4096
    OUTPUT_CALLBACK_CHUNK_SIZE: ClassVar[int] = 2 * 1024
    SUMMARY_MASK: ClassVar[str] = """
        Terminal `{id}` running `{command}` for {runtime}.
        Status: `{status}`; exit code: `{exit_code}`.
    """

    id: str | None = Field(default=None, description="Identifier used by the terminal management tools.")
    expression: Expression = Field(description="DSL expression being run.", exclude=True)
    timeout: int = Field(default=120, gt=0, description="Maximum execution time in seconds.")
    cwd: str = Field(description="Working directory used by the command.")
    status: TerminalStatus = TerminalStatus.CREATED
    output: str = ""
    exit_code: int | None = None
    on_complete: SkipJsonSchema[Callable[["Terminal"], None] | None] = Field(default=None, exclude=True)
    on_output: SkipJsonSchema[Callable[["Terminal"], None] | None] = Field(default=None, exclude=True)

    _read_offset: int = 0
    _output_callback_pending: bool = False
    _started_at: float = 0
    _finished_at: float = 0
    _process_handle: asyncio.subprocess.Process | None = None

    def model_post_init(self, __context) -> None:
        if not self.id:
            self.id = get_hash_readable(str(uuid4()), length=4)

    @cp
    def runtime(self) -> float:
        finished_at = self._finished_at or time.monotonic()
        return finished_at - self._started_at

    def tail(self, size: int) -> str:
        return self.output[-size:].strip()

    @cp
    def summary(self) -> str:
        command = strings.truncate_mid(str(self.expression), length=20)
        return strings.Mask(self.SUMMARY_MASK).format(
            id=self.id,
            command=command,
            cwd=self.cwd,
            runtime=humanize.precisedelta(self.runtime, format="%0.1f"),
            status=self.status,
            exit_code=self.exit_code,
        )

    @cp
    def process(self) -> asyncio.Task:
        self._started_at = time.monotonic()
        return asyncio.create_task(self._run())

    async def start(self) -> TerminalStatus:
        self.status = TerminalStatus.RUNNING
        self.process
        return self.status

    async def _read(self, stream: asyncio.StreamReader) -> None:
        while chunk := await stream.read(self.READ_CHUNK_SIZE):
            self.output += chunk.decode(errors="replace")
            if len(self.output) - self._read_offset < self.OUTPUT_CALLBACK_CHUNK_SIZE:
                continue
            if self._output_callback_pending or not self.on_output:
                continue

            self._output_callback_pending = True
            self.on_output(self)

    async def _run(self) -> None:
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
                asyncio.create_task(self._read(process.stdout)),
                asyncio.create_task(self._read(process.stderr)),
            ]
            try:
                await asyncio.wait_for(process.wait(), timeout=self.timeout)
            except TimeoutError:
                await self._terminate(process)
                self.status = TerminalStatus.TIMED_OUT
            except asyncio.CancelledError:
                await self._terminate(process)
                self.status = TerminalStatus.KILLED
                raise
            finally:
                await asyncio.gather(*readers)

            self.exit_code = process.returncode
            if self.status == TerminalStatus.RUNNING:
                self.status = TerminalStatus.COMPLETED if process.returncode == 0 else TerminalStatus.FAILED
        except asyncio.CancelledError:
            if self._process_handle:
                await self._terminate(self._process_handle)
            self.status = TerminalStatus.KILLED
            raise
        except OSError as error:
            self.status = TerminalStatus.FAILED
            self.output += str(error)
        finally:
            self._finished_at = time.monotonic()
            self._process_handle = None
            if self.on_complete:
                self.on_complete(self)

    async def _terminate(self, process: asyncio.subprocess.Process) -> None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        await process.wait()

    async def kill(self) -> TerminalStatus:
        if self.process.done():
            return self.status
        self.process.cancel()
        await asyncio.gather(self.process, return_exceptions=True)
        return self.status

    async def get(self) -> str:
        await asyncio.sleep(0)
        output = self.output[self._read_offset:]
        self._read_offset = len(self.output)
        self._output_callback_pending = False
        return output
