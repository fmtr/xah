import asyncio
from functools import cached_property
from typing import ClassVar

import humanize
from pydantic import Field
from acp.schema import FileEditToolCallContent, TerminalToolCallContent, ToolCallLocation

from corio import Constants, Path, strings
from corio.function import ccp, cp
from corio.hash import get_hash_readable
from corio.shell.dsl import Expression

from xah.class_collections import classes
from xah.toolsets.base.output import Output
from xah.toolsets.base.projection.base import ProjectionContent
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool, ValidationAbort

from xah.toolsets.terminal.terminal import Terminal


class TerminalOutput(Output):
    terminal: Terminal
    cwd_default: Path

    SUMMARY_MASK: ClassVar[str] = strings.trim("""
        Terminal `{id}` running `{command}` for {runtime}.
        Last output: {last_output} ago.
        Status: `{status}`; exit code: `{exit_code}`.
    """)
    MASK: ClassVar[str] = strings.trim("""
        {summary}
        Output is being written to: `{path}` ({size} bytes).

        ## Tail

        {tail}

        The above is the tail only. Review the output file directly if you need more.
    """)

    @property
    def path(self) -> Path:
        return self.terminal.output_path.relative_to(self.cwd_default)

    @property
    def summary(self) -> str:
        terminal = self.terminal
        command = strings.truncate_mid(str(terminal.expression), length=20)
        runtime = humanize.precisedelta(terminal.runtime, format="%0.1f")
        output_idle = humanize.precisedelta(terminal.output_idle, format="%0.1f")
        return strings.Mask(self.SUMMARY_MASK).format(
            id=terminal.id,
            command=command,
            cwd=terminal.cwd,
            runtime=runtime,
            status=terminal.status,
            exit_code=terminal.exit_code,
            last_output=output_idle,
        )

    @property
    def tail(self) -> str:
        return self.terminal.tail()

    @property
    def message(self) -> str:
        terminal = self.terminal
        return strings.Mask(self.MASK).format(
            summary=self.summary,
            path=self.path,
            size=terminal.output_size,
            tail=self.code_block(self.tail),
        )

    @property
    def agent(self) -> str:
        return self.message

    @property
    def command(self) -> str:
        return str(self.terminal.expression)

    COMMAND_LANGUAGE: ClassVar[str] = "bash"

    @property
    def title(self) -> str:
        return f"{self.request.input.title} {Constants.ARROW_RIGHT} `{self.terminal.status}`"

    @property
    def locations(self) -> list[ToolCallLocation]:
        return [ToolCallLocation(path=str(self.terminal.output_path))]

    @property
    def content(self) -> list[ProjectionContent]:
        output_path = str(self.terminal.output_path)
        command = self.code_block(self.command, language=self.COMMAND_LANGUAGE)
        return [
            #TerminalToolCallContent(type="terminal", terminal_id=self.terminal.id), # Unsupported in zed, and breaks other content.
            self.content_block(self.summary),
            self.content_block(command),
            FileEditToolCallContent(
                type="diff",
                path=output_path,
                old_text="",
                new_text=self.tail,
            ),


        ]


class TerminalStatuses(Output):
    terminals: list[Terminal]
    cwd_default: Path

    @property
    def agent(self) -> list[str]:
        return [
            TerminalOutput(terminal=terminal, cwd_default=self.cwd_default).agent
            for terminal in self.terminals
        ]


class TerminalToolBase(Tool):
    """Base for tools that address a managed terminal."""

    KIND = Kinds.OTHER

    @cp
    def terminal(self) -> Terminal:
        return self.terminals.id[self.terminal_id]

    @ccp
    def Output(cls) -> type[TerminalOutput]:
        return TerminalOutput

    @cp
    def output(self) -> TerminalOutput:
        return self.Output(
            terminal=self.terminal,
            cwd_default=self.ctx.deps.cwd_default,
        )

    @cached_property
    def terminals(self):
        from xah.toolsets.terminal.toolset import Terminals

        return self.ctx.deps.toolsets.all.cls[Terminals].terminals


class TerminalTool(TerminalToolBase):
    """Run a DSL subprocess expression as a managed background terminal."""

    QUICK_COMPLETION_TIMEOUT: ClassVar[int] = 5
    OUTPUT_MAX_CHARS: ClassVar[int] = 8 * 1024
    timeout: int | None = Field(default=None, description="Maximum execution time in seconds; None means no timeout.")

    def activate_async_tools(self) -> None:
        from xah.toolsets.fs.toolset import Files
        from xah.toolsets.utils.toolset import Utils

        for toolset_type in (Files, Utils):
            self.ctx.deps.toolsets.all.name[toolset_type.name].activated = True

    @cp
    def terminal_id(self) -> str:
        return get_hash_readable(self.call_id, length=4)

    def notify(self) -> str:
        message = strings.trim(f"""
            Terminal has changed state:

            {self.output.agent}
        """)
        self.feedback(message)
        return message

    @cached_property
    def expression(self) -> Expression:
        raise NotImplementedError

    @cached_property
    def output_path(self) -> Path:
        directory = self.ctx.deps.terminals_dir
        directory.mkdirf()
        executable_name = Path(self.expression.name).name
        return directory / f"{executable_name}-{self.terminal_id}.log"

    async def run(self) -> TerminalOutput:
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
            return self.output

        if terminal.output_size > self.OUTPUT_MAX_CHARS:
            self.activate_async_tools()
            return self.output

        return self.output


class ManagementInput(InputBase):
    terminal_id: str


class TerminalManagementTool(TerminalToolBase, ManagementInput):
    """Operate on an existing managed terminal."""

    EVENT: ClassVar[str]
    terminal_id: str = Field(description="Identifier of the background terminal.")

    @classes
    def Validators(cls):
        return [ExistingTerminal]


class ExistingTerminal(TerminalManagementTool):
    terminal_id: str | None

    async def validate(self):
        if self.terminal_id is None:
            return

        if self.terminal_id not in self.terminals.id:
            raise ValidationAbort(
                f"Terminal with ID '{self.terminal_id}' not found"
            )
