from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection

from xah.class_collections import classes
from xah.toolsets.base.tool import Input as InputBase, Kinds
from xah.toolsets.terminal.base import TerminalManagementTool, TerminalStatuses


class Input(InputBase):
    terminal_id: str | None = Field(default=None, description="Identifier of the background terminal.")

    def get_projection(self, request):
        if self.terminal_id is None:
            title = "List terminal statuses"
        else:
            title = f"Check terminal {self.terminal_id}"
        return AcpToolProjection(title=title)


class Status(Input, TerminalManagementTool):
    """Return the status and a short output tail of a background terminal."""

    KIND = Kinds.READ

    EVENT = "finished"

    @classes
    def Validators(cls):
        return [ExistingTerminal]

    async def run(self) -> str | TerminalStatuses:
        if self.terminal_id is None:
            return TerminalStatuses(terminals=list(self.terminals), cwd=self.cwd)

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
