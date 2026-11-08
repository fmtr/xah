from corio.function import ccp
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool


class Input(InputBase):
    @property
    def title(self):
        return "Reading todos"

    @property
    def projection(self):
        return AcpToolProjection(
            content=[self.content_block("Read current todo list")],
            title=self.title,
        )

    pass


class Read(Tool, Input):
    """Read the current todo list and task IDs."""

    KIND = Kinds.READ

    async def run(self) -> str:
        self.toolset.feedback_state(self)
        return self.toolset.text
