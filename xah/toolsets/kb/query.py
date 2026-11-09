from pydantic import Field
from qdrant_client.http import models

from corio import strings
from corio.db.search.document import Document
from xah.class_collections import classes
from xah.toolsets.base.output import Output
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.kb.db import WebPage
from xah.toolsets.kb.validators import CollectionValidator


class DocumentHitsOutput(Output):
    hits: list[Document]

    @property
    def agent(self) -> list[dict] | str:
        if not self.hits:
            return "The query returned no results."
        return self.model_dump(mode="json")["hits"]

    @property
    def content(self):
        if not self.hits:
            return [self.content_block(self.agent)]
        return super().content


class Input(InputBase):
    query: str = Field(
        description=strings.trim("""
        Text query to run against the document type.
        Note that this is a **semantic** search, not keyword.
        Stuffing the query with many semantically-similar keywords will not perform well.
        """)
    )
    collection_id: str = Field(description="Collection ID to search.")

    @property
    def title(self):
        query = self.preview(self.query, limit=20)
        return f"Searching knowledge `{self.collection_id}` for `{query}`"


class Query(Tool, Input):
    """Run a text query against a knowledgebase document type."""

    KIND = Kinds.SEARCH

    @classes
    def Validators(cls):
        return [CollectionValidator]

    async def run(self) -> DocumentHitsOutput:
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
            return DocumentHitsOutput(hits=[])

        from xah.toolsets.kb.get import Get
        msg=strings.trim(f"""
            These are excerpts matching your query only.
            Use the {self.toolset.get_name(Get)} tool to page through documents of interest.
        """)
        self.feedback(msg)

        return DocumentHitsOutput(hits=results.hits)
