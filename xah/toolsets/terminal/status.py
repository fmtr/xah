from pydantic import Field
from corio.function import ccp
from pydantic_acp.projection import ToolProjection as AcpToolProjection

from xah.class_collections import classes
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds
from xah.toolsets.terminal.base import TerminalManagementTool, TerminalOutput, TerminalStatuses


class StatusOutput(TerminalOutput):
    pass


class Input(InputBase):
    terminal_id: str | None = Field(default=None, description="Identifier of the background terminal.")

    @property
    def title(self):
        if self.terminal_id is None:
            return "Listing terminal statuses"
        return f"Checking terminal **{self.terminal_id}**"

    @property
    def projection(self):
        return AcpToolProjection(title=self.title)


class Status(Input, TerminalManagementTool):
    """Return the status and a short output tail of a background terminal."""

    @ccp
    def Output(cls) -> type[StatusOutput]:
        return StatusOutput

    KIND = Kinds.READ

    EVENT = "finished"

    @classes
    def Validators(cls):
        return [ExistingTerminal]

    async def run(self) -> str | TerminalStatuses:
        if self.terminal_id is None:
            return TerminalStatuses(
                terminals=list(self.terminals),
                cwd_default=self.ctx.deps.cwd_default,
            )

        return self.output


class ExistingTerminal(Status):
    async def validate(self):
        if self.terminal_id is None:
            return

        if self.terminal_id not in self.terminals.id:
            self.validation.messages.errors.append(
                f"Terminal with ID '{self.terminal_id}' not found"
            )
            self.validation.abort = True
