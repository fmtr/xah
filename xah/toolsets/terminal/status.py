from xah.class_collections import classes
from xah.toolsets.terminal.base import TerminalManagementTool


class Status(TerminalManagementTool):
    """Return the current status of a background terminal."""

    EVENT = "finished"

    @classes
    def Validators(cls):
        return [ExistingTerminal]

    async def run(self) -> str:
        return self.message


class ExistingTerminal(Status):
    async def validate(self):
        if self.terminal_id not in self.terminals.id:
            self.validation.messages.errors.append(
                f"Terminal with ID '{self.terminal_id}' not found"
            )
            self.validation.abort = True
