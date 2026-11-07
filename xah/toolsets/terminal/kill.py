from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.terminal.base import TerminalManagementTool, TerminalOutput


class Input(InputBase):
    terminal_id: str = Field(description="Identifier of the background terminal.")

    @property
    def projection(self):
        request = self.request
        return AcpToolProjection(title=f"Kill terminal {self.terminal_id}")


class Kill(Input, TerminalManagementTool):
    """Kill a background terminal process."""

    async def run(self) -> TerminalOutput:
        await self.terminal.kill()
        return self.output
