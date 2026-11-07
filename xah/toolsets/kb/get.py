from pydantic import Field

from xah.class_collections import classes
from corio import strings
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.output import Output
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from corio.db.search.document import Document
from xah.toolsets.kb.db import WebPage
from xah.toolsets.kb.validators import CollectionValidator


class DocumentChunksOutput(Output):
    chunks: list[Document]

    @property
    def agent(self) -> list[dict]:
        return self.model_dump(mode="json")["chunks"]


class Input(InputBase):
    collection_id: str = Field(description="Collection ID for the document to fetch chunks from.")
    document_id: str = Field(description="Document ID to fetch chunks from.")
    chunks: list[int] = Field(
        min_length=1,
        max_length=5,
        description="Chunk indexes to fetch; select at most five chunks.",
    )

    @property
    def projection(self):
        request = self.request
        chunks = strings.join_natural(str(chunk) for chunk in self.chunks)
        title = f"Getting chunks {chunks} from {self.document_id}"
        return AcpToolProjection(title=title)

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
