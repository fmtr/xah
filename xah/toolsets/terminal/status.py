from pydantic import Field
from corio.function import ccp
from xah.toolsets.base.projection import Projection as ProjectionBase

from xah.class_collections import classes
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase
from xah.toolsets.terminal.base import TerminalManagementTool


class Projection(ProjectionBase):
    def title(self):
        if self.sig.terminal_id is None:
            return "List terminal statuses"
        return f"Check terminal {self.sig.terminal_id}"


class Signature(SignatureBase):
    terminal_id: str | None = Field(default=None, description="Identifier of the background terminal.")


class Status(Signature, TerminalManagementTool):
    """Return the status and a short output tail of a background terminal."""

    @ccp
    def Projection(cls):
        return Projection

    KIND = Kinds.READ

    EVENT = "finished"

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
