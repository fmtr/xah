import asyncio

import humanize
from pydantic import Field
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool


class Input(InputBase):
    seconds: float = Field(default=10, ge=0, description="Number of seconds to wait.")

    @property
    def title(self):
        duration = humanize.precisedelta(self.seconds, format="%0.1f")
        return f"Sleeping for {duration}"



class Sleep(Tool, Input):
    """Pause for the specified number of seconds."""

    KIND = Kinds.OTHER

    async def run(self) -> str:
        await asyncio.sleep(self.seconds)
        duration = humanize.precisedelta(self.seconds, format="%0.1f")
        return f"Slept for {duration}."
