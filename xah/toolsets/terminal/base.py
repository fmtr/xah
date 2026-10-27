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

        terminal = self.terminal
        cwd = self.ctx.deps.options.cls[PathCwd].value
        path = terminal.output_path.relative_to(cwd)
        return strings.Mask(self.MASK).format(
            status=terminal.status,
            id=terminal.id,
            summary=terminal.summary,
            path=path,
            size=terminal.output_size,
        )


class TerminalTool(TerminalToolBase):
    """Run a DSL subprocess expression as a managed background terminal."""

    QUICK_COMPLETION_TIMEOUT: ClassVar[int] = 5
    OUTPUT_MAX_CHARS: ClassVar[int] = 8 * 1024
    timeout: int | None = Field(default=None, description="Maximum execution time in seconds; None means no timeout.")

    def activate_async_tools(self) -> None:
        from xah.toolsets.fs.toolset import Files
        from xah.toolsets.utils.toolset import Utils

        for toolset_type in (Files, Utils):
            self.ctx.deps.toolsets.all.cls[toolset_type].activated = True

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
        await terminal.start()
        try:
            await asyncio.wait_for(
                asyncio.shield(terminal.process),
                timeout=self.QUICK_COMPLETION_TIMEOUT,
            )
        except TimeoutError:
            if not terminal.process.done():
                self.activate_async_tools()
                terminal.on_status = self.notify
            return self.message

        if terminal.output_size > self.OUTPUT_MAX_CHARS:
            self.activate_async_tools()
            return self.message

        return await terminal.get()


class TerminalManagementTool(TerminalToolBase):
    """Operate on an existing managed terminal."""

    EVENT: ClassVar[str]
    terminal_id: str = Field(description="Identifier of the background terminal.")

