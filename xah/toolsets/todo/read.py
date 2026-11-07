from corio.function import ccp
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.tool import Input as InputBase, Kinds, Tool


class Input(InputBase):
    def get_projection(self, request):
        return AcpToolProjection(content=[self.content_block("Read current todo list")], title="Read todos")

    pass


class Read(Tool, Input):
    """Read the current todo list and task IDs."""

    KIND = Kinds.READ

    async def run(self) -> str:
        self.toolset.feedback_state(self)
        return self.toolset.text
