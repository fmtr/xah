from pydantic import Field

from xah.class_collections import classes
from xah.toolsets.base.tool import Tool
from xah.toolsets.kb.db import WebPage
from xah.toolsets.kb.validators import CollectionValidator


class Get(Tool):
    """Used to page through documents of interest found by search."""

    id: str = Field(description="Collection ID for the document to fetch chunks from.")
    chunks: list[int] = Field(
        min_length=1,
        max_length=5,
        description="Chunk indexes to fetch; select at most five chunks.",
    )

    @classes
    def Validators(cls):
        return [CollectionValidator]

    async def run(self) -> list:
        collection = self.toolset.collection_for(self.id)
        return await collection.get_chunks(
            client=self.toolset.client,
            id=self.id,
            chunks=self.chunks,
        )
