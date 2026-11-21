import asyncio
from functools import cached_property
from typing import ClassVar

import humanize
from pydantic import Field
from acp.schema import FileEditToolCallContent, TerminalToolCallContent, ToolCallLocation

from corio import Constants, Path, env, strings
from corio.function import ccp, cp
from corio.hash import get_hash_readable
from corio.shell.dsl.expression import Expression

from xah.class_collections import classes
from xah.toolsets.base.output import Output
from xah.toolsets.base.projection.base import ProjectionContent
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool, ValidationAbort

from xah.toolsets.terminal.terminal import (
    TERMINAL_INLINE_OUTPUT_MAX_CHARS,
    Terminal,
    TerminalStatus,
)


class TerminalOutput(Output):
    terminal: Terminal
    cwd_default: Path
    show_full_output: bool = Field(default=False, exclude=True)

    SUMMARY_MASK: ClassVar[str] = strings.trim("""
        Terminal `{id}` running `{command}` for {runtime}.
        Last output: {last_output} ago.
        Status: `{status}`; exit code: `{exit_code}`.
    """)
    MASK: ClassVar[str] = strings.trim("""
        {summary}
        {output_location}

        ## {output_heading}

        {output_text}

        {output_note}
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
    def displayed_output(self) -> str:
        if self.show_full_output:
            return self.terminal.read_output(TERMINAL_INLINE_OUTPUT_MAX_CHARS + 1)

        return self.tail

    @property
    def output_heading(self) -> str:
        if self.show_full_output:
            return "Full output"

        return "Recent output"

    @property
    def output_note(self) -> str:
        if self.show_full_output:
            return ""

        return f"The tail contains at most {self.terminal.TAIL_LENGTH} bytes."

    @property
    def output_requires_file_reference(self) -> bool:
        terminal = self.terminal
        if terminal.was_background:
            return True

        output_prefix = terminal.read_output(TERMINAL_INLINE_OUTPUT_MAX_CHARS + 1)
        return len(output_prefix) > TERMINAL_INLINE_OUTPUT_MAX_CHARS

    @property
    def output_location(self) -> str:
        terminal = self.terminal
        if terminal.status in {TerminalStatus.CREATED, TerminalStatus.RUNNING}:
            return strings.trim(f"""
                Output is being written to: `{self.path}` ({terminal.output_size} bytes).
                Use the Files and Terminals tools to inspect or manage it.
            """)

        if terminal.was_background:
            return strings.trim(f"""
                Terminal output is available at: `{self.path}` ({terminal.output_size} bytes).
                Use the Files and Terminals tools to inspect it.
            """)

        if self.output_requires_file_reference:
            return strings.trim(f"""
                Output exceeded {TERMINAL_INLINE_OUTPUT_MAX_CHARS} characters.
                Full output is available at: `{self.path}` ({terminal.output_size} bytes).
                Use the Files tools to inspect it.
            """)

        return "Full output was returned inline."

    @property
    def message(self) -> str:
        return strings.Mask(self.MASK).format(
            summary=self.summary,
            output_location=self.output_location,
            output_heading=self.output_heading,
            output_text=self.code_block(self.displayed_output),
            output_note=self.output_note,
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
        content = [
            #TerminalToolCallContent(type="terminal", terminal_id=self.terminal.id), # Unsupported in zed, and breaks other content.
            self.content_block(self.summary),
            self.content_block(command),
            FileEditToolCallContent(
                type="diff",
                path=output_path,
                old_text="",
                new_text=self.displayed_output,
            ),
        ]
        if not self.show_full_output:
            content.append(self.content_block("Tail only"))

        return content


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
    EXTERNALIZE_OUTPUT: ClassVar[bool] = False
    timeout: int | None = Field(default=None, description="Maximum execution time in seconds; None means no timeout.")

    def activate_output_tools(self) -> None:
        from xah.toolsets.fs.toolset import Files
        from xah.toolsets.terminal.toolset import Terminals

        for toolset_type in (Files, Terminals):
            self.ctx.deps.toolsets.all.name[toolset_type.name].activated = True

    def activate_async_tools(self) -> None:
        from xah.toolsets.utils.toolset import Utils

        self.activate_output_tools()
        self.ctx.deps.toolsets.all.name[Utils.name].activated = True

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

    @property
    def env(self) -> dict[str, str]:
        return env.get_dict()

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
            env=self.env,
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
                terminal.was_background = True
                self.activate_async_tools()
                terminal.on_status = self.notify
                return self.output

        output_text = terminal.read_output(TERMINAL_INLINE_OUTPUT_MAX_CHARS + 1)
        if len(output_text) > TERMINAL_INLINE_OUTPUT_MAX_CHARS:
            self.activate_output_tools()
            return self.output

        output = self.output
        output.show_full_output = True
        return output


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
