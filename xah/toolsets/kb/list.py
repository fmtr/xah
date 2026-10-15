from xah.toolsets.base.tool import Tool
from xah.toolsets.kb.history import ResearchHistory


class List(Tool):
    """List known research collections and fixed document collections."""

    async def run(self) -> list[ResearchHistory]:
        history = self.toolset.history
        research = [
            ResearchHistory.model_validate(entry.model_dump())
            for entry in history
        ]
        fixed = [collection.history for collection in self.toolset.Collections]
        return research + fixed
