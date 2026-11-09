from pydantic import Field

from xah.class_collections import classes
from corio import strings
from xah.toolsets.base.output import Output
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from corio.db.search.document import Document
from xah.toolsets.kb.db import WebPage
from xah.toolsets.kb.validators import CollectionValidator


class DocumentChunksOutput(Output):
    chunks: list[Document]

    @property
    def agent(self) -> list[dict] | str:
        if not self.chunks:
            return "No chunks were found for the requested document."
        return self.model_dump(mode="json")["chunks"]

    @property
    def content(self):
        if not self.chunks:
            return [self.content_block(self.agent)]
        return super().content


class Input(InputBase):
    collection_id: str = Field(description="Collection ID for the document to fetch chunks from.")
    document_id: str = Field(description="Document ID to fetch chunks from.")
    chunks: list[int] = Field(
        min_length=1,
        max_length=5,
        description="Chunk indexes to fetch; select at most five chunks.",
    )

    @property
    def title(self):
        chunk_count = strings.suffix_plural(len(self.chunks), "chunk")
        return f"Getting {chunk_count} from knowledge `{self.collection_id}` for `{self.document_id}`"


class Get(Tool, Input):
    """Used to page through documents of interest found by search."""

    KIND = Kinds.READ

    @classes
    def Validators(cls):
        return [CollectionValidator]

    async def run(self) -> DocumentChunksOutput:
        collection = self.toolset.collection_for(self.collection_id)
        chunks = await collection.get_chunks(
            client=self.toolset.client,
            id=self.document_id,
            chunks=self.chunks,
        )
        return DocumentChunksOutput(chunks=chunks)
