import asyncio
import os
import signal
from functools import cached_property

from pydantic import Field
from pydantic_ai import ToolFailed

from corio import strings
from corio.shell.dsl import Expression
from xah.toolsets.base.tool import Tool


MAX_EXECUTE_OUTPUT = 100_000


class SubprocessRunner(Tool):
    timeout: int | None = Field(default=120, gt=0, description="Maximum execution time in seconds.")

    @cached_property
    def expression(self) -> Expression:
        raise NotImplementedError

    async def terminate(self, process) -> None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.communicate()

    async def run(self) -> str:
        command = self.expression.name
        tokens = self.expression.tokens(args_only=True)
        try:
            process = await asyncio.create_subprocess_exec(
                command,
                *(tokens or []),
                cwd=str(self.cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                start_new_session=True,
            )
        except OSError as error:
            raise ToolFailed(str(error)) from error

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )
        except TimeoutError as error:
            await self.terminate(process)
            raise ToolFailed(
                f"Command timed out after {self.timeout} seconds.",
            ) from error
        except asyncio.CancelledError:
            await self.terminate(process)
            raise

        output = (stdout + stderr).decode(errors="replace")
        if len(output) > MAX_EXECUTE_OUTPUT:
            output = strings.trim(
                output[:MAX_EXECUTE_OUTPUT],
                "... (output truncated)",
            )
        if process.returncode:
            message = strings.trim(
                f"Command failed (exit code {process.returncode}):",
                output,
            )
            raise ToolFailed(message)
        return output
