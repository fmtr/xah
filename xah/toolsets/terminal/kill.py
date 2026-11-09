from pydantic import Field
from corio.function import ccp
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.terminal.base import TerminalManagementTool, TerminalOutput


class KillOutput(TerminalOutput):
    pass


class Input(InputBase):
    terminal_id: str = Field(description="Identifier of the background terminal.")

    @property
    def title(self):
        return f"Stopping terminal `{self.terminal_id}`"



class Kill(Input, TerminalManagementTool):
    """Kill a background terminal process."""

    @ccp
    def Output(cls) -> type[KillOutput]:
        return KillOutput

    async def run(self) -> TerminalOutput:
        await self.terminal.kill()
        return self.output
