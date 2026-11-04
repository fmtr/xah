from pydantic import Field
from corio.function import ccp
from xah.toolsets.base.projection import Projection as ProjectionBase
from xah.toolsets.base.tool import Signature as SignatureBase
from xah.toolsets.terminal.base import TerminalManagementTool


class Projection(ProjectionBase):
    def title(self):
        return f"Kill terminal {self.sig.terminal_id}"


class Signature(SignatureBase):
    terminal_id: str = Field(description="Identifier of the background terminal.")


class Kill(Signature, TerminalManagementTool):
    """Kill a background terminal process."""

    @ccp
    def Projection(cls):
        return Projection

    async def run(self) -> str:
        status = await self.terminal.kill()
        return f"Terminal `{self.terminal.id}` has status `{status}`."
