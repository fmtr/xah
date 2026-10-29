from pydantic import Field

from xah.class_collections import classes
from xah.toolsets.terminal.base import TerminalManagementTool


class Status(TerminalManagementTool):
    """Return the status and a short output tail of a background terminal."""

    EVENT = "finished"
    terminal_id: str | None = Field(
        default=None,
        description="Identifier of the background terminal. Leave empty to return summaries for all managed terminals.",
    )

    @classes
    def Validators(cls):
        return [ExistingTerminal]

    async def run(self) -> str | list[str]:
        if self.terminal_id is None:
            return [terminal.summary for terminal in self.terminals]

        return self.message


class ExistingTerminal(Status):
    async def validate(self):
        if self.terminal_id is None:
            return

        if self.terminal_id not in self.terminals.id:
            self.validation.messages.errors.append(
                f"Terminal with ID '{self.terminal_id}' not found"
            )
            self.validation.abort = True
