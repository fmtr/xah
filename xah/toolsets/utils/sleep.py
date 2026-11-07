import asyncio

from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.tool import Input as InputBase, Kinds, Tool


class Input(InputBase):
    seconds: float = Field(default=10, ge=0, description="Number of seconds to wait.")

    def get_projection(self, request):
        title = f"Sleeping for {self.seconds:g} seconds"
        return AcpToolProjection(title=title)


class Sleep(Tool, Input):
    """Pause for the specified number of seconds."""

    KIND = Kinds.OTHER

    async def run(self) -> str:
        await asyncio.sleep(self.seconds)
        return f"Slept for {self.seconds:g} seconds."
