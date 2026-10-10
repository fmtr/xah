import asyncio
from functools import cached_property, partial
from typing import ClassVar

from pydantic import Field
from pydantic_ai import RunContext

from corio import strings
from corio.shell.dsl import Expression
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.toolset import Toolset
from xah.toolsets.terminal.terminal import Terminal


class TerminalTool(Tool):
    """Run a DSL subprocess expression as a managed background terminal."""

    QUICK_COMPLETION_TIMEOUT: ClassVar[int] = 5
    OUTPUT_MAX_CHARS: ClassVar[int] = 8 * 1024
    TRUNCATION_MASK: ClassVar[str] = """
        [{lines} lines truncated]
        {tail}
    """
    TRUNCATION_FEEDBACK: ClassVar[str] = """
        Command output was truncated because it exceeded {chars} characters.
        Please run commands that produce less output in future, such as by filtering or limiting the results.
    """
    timeout: int = Field(default=120, gt=0, description="Maximum execution time in seconds.")

    @cached_property
    def expression(self) -> Expression:
        raise NotImplementedError

    @classmethod
    def truncate_output(cls, output: str) -> str:
        if len(output) <= cls.OUTPUT_MAX_CHARS:
            return output

        omitted = output[:-cls.OUTPUT_MAX_CHARS]
        truncated_lines = len(omitted.splitlines())
        tail = output[-cls.OUTPUT_MAX_CHARS:]
        return strings.Mask(cls.TRUNCATION_MASK).format(lines=truncated_lines, tail=tail)

    @cached_property
    def terminals(self):
        from xah.toolsets.terminal.toolset import Terminals

        return self.ctx.deps.toolsets.cls[Terminals].terminals

    async def run(self) -> str:
        from xah.toolsets.terminal.output import Output
        from xah.toolsets.terminal.status import Status

        terminal = Terminal(
            expression=self.expression,
            timeout=self.timeout,
            cwd=str(self.cwd),
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
            terminal.on_output = partial(Output.notify, self.ctx)
            return f"Started terminal `{terminal.id}` with status `{status}`. Use terminal_id `{terminal.id}` with the other Terminal tools."

        output = await terminal.get()
        if len(output) > self.OUTPUT_MAX_CHARS: # todo: this should probably be a validator, but awkward as Terminal.get advances the cursor.
            feedback = strings.Mask(self.TRUNCATION_FEEDBACK).format(chars=self.OUTPUT_MAX_CHARS)
            self.feedback(feedback)

        return self.truncate_output(output)


class TerminalManagementTool(Tool):
    """Operate on an existing managed terminal."""

    EVENT: ClassVar[str]
    TAIL_SIZE: ClassVar[int] = 512
    MASK: ClassVar[str] = """
        Terminal {event}.
        {summary}

        ```
        {tail}
        ```
        
        Note: The above is the output tail only. Use the {tool} tool to inspect its full output.
    """
    terminal_id: str = Field(description="Identifier of the background terminal.")

    @classmethod
    def notify(cls, ctx: RunContext, terminal: Terminal) -> None:
        from xah.toolsets.terminal.output import Output

        event = cls.EVENT.format(status=terminal.status)
        message = strings.Mask(cls.MASK).format(
            id=terminal.id,
            event=event,
            summary=terminal.summary,
            tail=terminal.tail(cls.TAIL_SIZE) or "[No New Output]",
            tool=Output.local_name,
        )
        Toolset.feedback(ctx, message)

    @cached_property
    def terminals(self):
        from xah.toolsets.terminal.toolset import Terminals

        return self.ctx.deps.toolsets.cls[Terminals].terminals

    @cached_property
    def terminal(self) -> Terminal:
        return self.terminals.id[self.terminal_id]
