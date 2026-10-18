from pydantic import Field
from pydantic_ai import ToolFailed, ModelRetry
from qdrant_client.http import models

from corio import strings
from corio.db.search.document import Document
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

    async def run(self) -> list[Document]:
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

        results = await anext(
            collection.query(
                texts=[self.query],
                client=self.toolset.client,
                runtime_filter=runtime_filter,
            )
        )

        if not results.hits:
            raise ModelRetry("The query returned no results.")

        from xah.toolsets.kb.get import Get
        msg=strings.trim(f"""
            These are excepts matching your query only.
            Use the {self.toolset.tool_name(Get)} tool to page through documents of interest.
        """)
        self.feedback(msg)

        return results.hits
