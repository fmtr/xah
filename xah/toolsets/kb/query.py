from pydantic import Field
from pydantic_ai import ToolFailed
from qdrant_client.http import models

from corio import strings
from xah.class_collections import classes
from xah.toolsets.base.tool import Tool
from xah.toolsets.kb.db import WebPage
from xah.toolsets.kb.validators import CollectionValidator


class Query(Tool):
    """Run a text query against a knowledgebase document type."""

    query: str = Field(
        description=strings.trim("""
        Text query to run against the document type.
        Note that this is a **semantic** search, not keyword.
        Stuffing the query with many semantically-similar keywords will not perform well.
        """)
    )
    collection_id: str = Field(description="Collection ID to search.")

    @classes
    def Validators(cls):
        return [CollectionValidator]

    async def run(self) -> list:
        collection = self.toolset.collection_for(self.collection_id)
        runtime_filter = None
        if collection is WebPage:
            runtime_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="collection_id",
                        match=models.MatchValue(value=self.collection_id),
                    )
                ]
            )

        try:
            results = await anext(
                collection.query(
                    texts=[self.query],
                    client=self.toolset.client,
                    runtime_filter=runtime_filter,
                )
            )
        except ValueError as error:
            raise ToolFailed(
                "The knowledgebase is not ready for this collection: "
                f"the {collection.name} collection does not exist yet. "
                "Continue without the knowledgebase query, or retry after documents have been indexed."
            ) from error

        return results.hits
