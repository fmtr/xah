from corio.function import ccp
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.output import Output
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.kb.history import ResearchHistory


class KnowledgeCollectionsOutput(Output):
    collections: list[ResearchHistory]

    @property
    def agent(self) -> list[dict]:
        return self.model_dump(mode="json")["collections"]


class Input(InputBase):
    @property
    def projection(self):
        request = self.request
        return AcpToolProjection(title="List knowledge collections")

    pass


class List(Tool, Input):
    """List known research collections and fixed document collections."""

    KIND = Kinds.READ

    async def run(self) -> KnowledgeCollectionsOutput:
        history = self.toolset.history
        research = [
            ResearchHistory.model_validate(entry.model_dump())
            for entry in history
        ]
        fixed = [collection.history for collection in self.toolset.Collections]
        return KnowledgeCollectionsOutput(collections=research + fixed)
