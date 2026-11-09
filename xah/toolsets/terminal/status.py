from pydantic import Field
from corio import Constants
from corio.function import ccp
from pydantic_acp.projection import ToolProjection as AcpToolProjection

from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds
from xah.toolsets.terminal.base import TerminalManagementTool, TerminalOutput, TerminalStatuses


class StatusOutput(TerminalOutput):
    @property
    def title(self) -> str:
        command = self.preview(self.command, limit=20)
        return f"{self.request.input.title} {Constants.ARROW_RIGHT} `{self.terminal.status}` `{command}`"


class Input(InputBase):
    terminal_id: str | None = Field(default=None, description="Identifier of the background terminal.")

    @property
    def title(self):
        if self.terminal_id is None:
            return "Listing terminal statuses"
        return f"Checking terminal `{self.terminal_id}`"

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

    async def run(self) -> str | TerminalStatuses:
        if self.terminal_id is None:
            return TerminalStatuses(
                terminals=list(self.terminals),
                cwd_default=self.ctx.deps.cwd_default,
            )

        return self.output
