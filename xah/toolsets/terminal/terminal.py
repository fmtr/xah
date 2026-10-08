import asyncio
import os
import signal
from collections.abc import Callable
from enum import StrEnum
from typing import ClassVar
from uuid import uuid4

from pydantic import Field
from pydantic.json_schema import SkipJsonSchema

from corio import Path, dm
from corio.function import cp
from corio.hash import get_hash_readable


class TerminalStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    TIMED_OUT = "timed_out"
    KILLED = "killed"
    FAILED = "failed"


class Terminal(dm.Base):
    """A background shell process whose output can be read incrementally."""

    READ_CHUNK_SIZE: ClassVar[int] = 4096
    OUTPUT_CALLBACK_CHUNK_SIZE: ClassVar[int] = 2 * 1024

    id: str | None = Field(default=None, description="Identifier used by the terminal management tools.")
    command: str = Field(description="Shell command being run.")
    shell: Path = Field(description="Shell executable used by the command.")
    timeout: int = Field(default=120, gt=0, description="Maximum execution time in seconds.")
    cwd: str = Field(description="Working directory used by the command.")
    status: TerminalStatus = TerminalStatus.CREATED
    output: str = ""
    exit_code: int | None = None
    on_complete: SkipJsonSchema[Callable[["Terminal"], None] | None] = Field(default=None, exclude=True)
    on_output: SkipJsonSchema[Callable[["Terminal"], None] | None] = Field(default=None, exclude=True)

    _read_offset: int = 0
    _output_callback_pending: bool = False
    _process_handle: asyncio.subprocess.Process | None = None

    def model_post_init(self, __context) -> None:
        if not self.id:
            self.id = get_hash_readable(str(uuid4()), length=4)

    @cp
    def process(self) -> asyncio.Task:
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
            process = await asyncio.create_subprocess_shell(
                self.command,
                cwd=self.cwd,
                executable=self.shell,
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
