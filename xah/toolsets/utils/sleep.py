import asyncio

from pydantic import Field

from xah.toolsets.base.tool import Tool


class Sleep(Tool):
    """Pause for the specified number of seconds."""

    seconds: float = Field(
        default=5,
        ge=0,
        le=120,
        description="Number of seconds to wait, from 0 to 120.",
    )

    async def run(self) -> str:
        await asyncio.sleep(self.seconds)
        return f"Slept for {self.seconds:g} seconds."
