from corio import strings
from xah.toolsets.base.output import Output
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.kb.history import ResearchHistory


class KnowledgeCollectionsOutput(Output):
    collections: list[ResearchHistory]

    @property
    def agent(self) -> list[dict]:
        return self.model_dump(mode="json")["collections"]

    @property
    def title(self) -> str:
        collection_ids = strings.join_natural(
            (collection.id for collection in self.collections),
            mask="`{}`",
        )
        return f"Listed collections {collection_ids}"

    @property
    def content(self):
        return [
            self.content_block(
                strings.trim(f"## `{collection.id}`", collection.desc)
            )
            for collection in self.collections
        ]


class Input(InputBase):
    @property
    def title(self):
        return "Listing knowledge collections"

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
