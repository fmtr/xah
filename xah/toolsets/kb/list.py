from corio.function import ccp
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.projection import Projection as ProjectionBase
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase, Tool
from xah.toolsets.kb.history import ResearchHistory


class Projection(ProjectionBase):
    def start(self):
        return AcpToolProjection(title="List knowledge collections")


class Signature(SignatureBase):
    pass


class List(Tool, Signature):
    """List known research collections and fixed document collections."""

    KIND = Kinds.READ

    @ccp
    def Projection(cls):
        return Projection

    async def run(self) -> list[ResearchHistory]:
        history = self.toolset.history
        research = [
            ResearchHistory.model_validate(entry.model_dump())
            for entry in history
        ]
        fixed = [collection.history for collection in self.toolset.Collections]
        return research + fixed
