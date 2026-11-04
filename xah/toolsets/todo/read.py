from corio.function import ccp
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.todo.projection import TodoProjection
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase, Tool


class Projection(TodoProjection):
    def start(self):
        return AcpToolProjection(content=[self.content("Read current todo list")], title="Read todos")


class Signature(SignatureBase):
    pass


class Read(Tool, Signature):
    """Read the current todo list and task IDs."""

    KIND = Kinds.READ

    @ccp
    def Projection(cls):
        return Projection

    async def run(self) -> str:
        self.toolset.feedback_state(self)
        return self.toolset.text
