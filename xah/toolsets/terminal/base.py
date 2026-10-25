import asyncio
from functools import cached_property, partial
from typing import ClassVar

from pydantic import Field
from pydantic_ai import RunContext

from corio import Path, strings
from corio.shell.dsl import Expression
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.toolset import Toolset
from xah.toolsets.terminal.terminal import Terminal


class TerminalTool(Tool):
    """Run a DSL subprocess expression as a managed background terminal."""

    QUICK_COMPLETION_TIMEOUT: ClassVar[int] = 5
    OUTPUT_MAX_CHARS: ClassVar[int] = 8 * 1024
    TRUNCATION_FEEDBACK: ClassVar[str] = strings.trim("""
        Command output was not returned inline because it exceeded {chars} characters.
        Use the output path to inspect the complete output.
    """)
    timeout: int = Field(default=120, gt=0, description="Maximum execution time in seconds.")

    @cached_property
    def expression(self) -> Expression:
        raise NotImplementedError

    @cached_property
    def terminals(self):
        from xah.toolsets.terminal.toolset import Terminals

        return self.ctx.deps.toolsets.all.cls[Terminals].terminals

    @cached_property
    def output_path(self) -> Path:
        settings = self.ctx.deps.settings
        directory = self.ctx.deps.cwd_default / settings.path.home.name / "terminals"
        directory.mkdirf()
        return directory / f"{self.expression.name}-{self.call_id}.log"

    async def run(self) -> str:
        from xah.toolsets.terminal.status import Status

        terminal = Terminal(
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
            terminal.on_complete = partial(Status.notify, self.ctx)
            return f"Started terminal `{terminal.id}` with status `{status}`. Use terminal_id `{terminal.id}` with the other Terminal tools."

        if terminal.output_size > self.OUTPUT_MAX_CHARS:
            feedback = strings.Mask(self.TRUNCATION_FEEDBACK).format(chars=self.OUTPUT_MAX_CHARS)
            self.feedback(feedback)
            return f"Terminal `{terminal.id}` completed. Full output is available at `{terminal.output_path}`."

        return await terminal.get()


class TerminalManagementTool(Tool):
    """Operate on an existing managed terminal."""

    EVENT: ClassVar[str]
    MASK: ClassVar[str] = strings.trim("""
        Terminal {event}.
        {summary}
        Output: `{path}` ({size} bytes).
    """)
    terminal_id: str = Field(description="Identifier of the background terminal.")

    @classmethod
    def notify(cls, ctx: RunContext, terminal: Terminal) -> None:
        event = cls.EVENT.format(status=terminal.status)
        message = strings.Mask(cls.MASK).format(
            id=terminal.id,
            event=event,
            summary=terminal.summary,
            path=terminal.output_path,
            size=terminal.output_size,
        )
        Toolset.feedback(ctx, message)

    @cached_property
    def terminals(self):
        from xah.toolsets.terminal.toolset import Terminals

        return self.ctx.deps.toolsets.all.cls[Terminals].terminals

    @cached_property
    def terminal(self) -> Terminal:
        return self.terminals.id[self.terminal_id]
