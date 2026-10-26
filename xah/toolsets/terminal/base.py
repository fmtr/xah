import asyncio
from functools import cached_property
from typing import ClassVar

from pydantic import Field

from corio import Path, strings
from corio.function import cp
from corio.hash import get_hash_readable
from corio.shell.dsl import Expression

from xah.toolsets.base.tool import Tool

from xah.toolsets.terminal.terminal import Terminal


class TerminalToolBase(Tool):
    """Base for tools that address a managed terminal."""

    MASK: ClassVar[str] = strings.trim("""
        {summary}
        Output is being written to: `{path}` ({size} bytes).
        Use `{toolset}` tools to monitor output tail, etc.
    """)

    @cp
    def terminal(self) -> Terminal:
        return self.terminals.id[self.terminal_id]

    @cached_property
    def terminals(self):
        from xah.toolsets.terminal.toolset import Terminals

        return self.ctx.deps.toolsets.all.cls[Terminals].terminals

    @property
    def message(self) -> str:
        from xah.options.path import PathCwd
        from xah.toolsets.fs.toolset import Files

        terminal = self.terminal
        cwd = self.ctx.deps.options.cls[PathCwd].value
        path = terminal.output_path.relative_to(cwd)
        return strings.Mask(self.MASK).format(
            status=terminal.status,
            id=terminal.id,
            summary=terminal.summary,
            path=path,
            size=terminal.output_size,
            toolset=Files.name,
        )


class TerminalTool(TerminalToolBase):
    """Run a DSL subprocess expression as a managed background terminal."""

    QUICK_COMPLETION_TIMEOUT: ClassVar[int] = 5
    OUTPUT_MAX_CHARS: ClassVar[int] = 8 * 1024
    TRUNCATION_FEEDBACK: ClassVar[str] = strings.trim("""
        Command output was not returned inline because it exceeded {chars} characters.
        Use the output path to inspect the complete output.
    """)
    timeout: int = Field(default=120, gt=0, description="Maximum execution time in seconds.")

    @cp
    def terminal_id(self) -> str:
        return get_hash_readable(self.call_id, length=4)

    def notify(self) -> str:
        message = strings.trim(f"""
            Terminal has changed state:

            {self.message}
        """)
        self.feedback(message)
        return message

    @cached_property
    def expression(self) -> Expression:
        raise NotImplementedError

    @cached_property
    def output_path(self) -> Path:
        settings = self.ctx.deps.settings
        directory = self.ctx.deps.cwd_default / settings.path.home.name / "terminals"
        directory.mkdirf()
        executable_name = Path(self.expression.name).name
        return directory / f"{executable_name}-{self.terminal_id}.log"

    async def run(self) -> str:
        terminal = Terminal(
            id=self.terminal_id,
            expression=self.expression,
            timeout=self.timeout,
            cwd=str(self.cwd),
            output_path=self.output_path,
        )
        self.terminals.append(terminal)
        status = await terminal.start()
        try:
            await asyncio.wait_for(
                asyncio.shield(terminal.process),
                timeout=self.QUICK_COMPLETION_TIMEOUT,
            )
        except TimeoutError:
            if not terminal.process.done():
                terminal.on_status = self.notify
            return f"Started terminal `{terminal.id}` with status `{status}`. Use terminal_id `{terminal.id}` with the other Terminal tools."

        if terminal.output_size > self.OUTPUT_MAX_CHARS:
            feedback = strings.Mask(self.TRUNCATION_FEEDBACK).format(chars=self.OUTPUT_MAX_CHARS)
            self.feedback(feedback)
            return f"Terminal `{terminal.id}` completed. Full output is available at `{terminal.output_path}`."

        return await terminal.get()


class TerminalManagementTool(TerminalToolBase):
    """Operate on an existing managed terminal."""

    EVENT: ClassVar[str]
    terminal_id: str = Field(description="Identifier of the background terminal.")

