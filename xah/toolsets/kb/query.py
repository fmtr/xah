from pydantic import Field
from pydantic_ai import ToolFailed
from qdrant_client.http import models

from corio import strings

from xah.toolsets.base.tool import Tool
from xah.toolsets.kb.db import WebPage


class Query(Tool):
    """Run a text query against a knowledgebase document type."""

    query: str = Field(
        description=strings.trim("""
        Text query to run against the document type.
        Note that this is a **semantic** search, not keyword.
        Stuffing the query with many semantically-similar keywords will not perform well.
        """)
    )
    research_id: str = Field(
        description="Limit results to pages assembled by this research run.",
    )

    async def run(self) -> list[WebPage]:
        runtime_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="research_id",
                    match=models.MatchValue(value=self.research_id),
                )
            ]
        )
        try:
            results = await anext(
                WebPage.query(
                    texts=[self.query],
                    client=self.toolset.client,
                    runtime_filter=runtime_filter,
                )
            )
        except ValueError as error:
            raise ToolFailed(
                "The knowledgebase is not ready for this research run: "
                "the WebPage collection does not exist yet. "
                "Continue without the knowledgebase query, or retry after pages have been indexed."
            ) from error

        return results.hits
