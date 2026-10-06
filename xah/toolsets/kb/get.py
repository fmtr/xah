from pydantic import Field

from xah.toolsets.base.tool import Tool
from xah.toolsets.kb.db import WebPage


class Get(Tool):
    """

    Used to page through documents of interest found by search

    """

    id: str = Field(description="Document ID to fetch chunks from.")
    chunks: list[int] = Field(
        min_length=1,
        max_length=5,
        description="Chunk indexes to fetch; select at most five chunks.",
    )

    async def run(self) -> list:
        return WebPage.get_chunks(
            client=self.toolset.client,
            id=self.id,
            chunks=self.chunks,
        )
