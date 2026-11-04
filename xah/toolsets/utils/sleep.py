import asyncio

from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from corio.function import ccp
from xah.toolsets.base.projection import Projection as ProjectionBase
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase, Tool


class Projection(ProjectionBase):
    def start(self):
        return AcpToolProjection(title=f"Sleeping for {self.sig.seconds:g} seconds")


class Signature(SignatureBase):
    seconds: float = Field(default=10, ge=0, description="Number of seconds to wait.")


class Sleep(Tool, Signature):
    """Pause for the specified number of seconds."""

    KIND = Kinds.OTHER

    @ccp
    def Projection(cls):
        return Projection

    async def run(self) -> str:
        await asyncio.sleep(self.seconds)
        return f"Slept for {self.seconds:g} seconds."
