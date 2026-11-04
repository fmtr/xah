from pydantic import Field

from xah.class_collections import classes
from corio import strings
from corio.function import ccp
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase, Tool
from xah.toolsets.kb.projection import KnowledgebaseProjection
from xah.toolsets.kb.db import WebPage
from xah.toolsets.kb.validators import CollectionValidator


class Projection(KnowledgebaseProjection):
    def title(self) -> str:
        chunks = strings.join_natural(str(chunk) for chunk in self.sig.chunks)
        return f"Getting chunks {chunks} from {self.sig.document_id}"


class Signature(SignatureBase):
    collection_id: str = Field(description="Collection ID for the document to fetch chunks from.")
    document_id: str = Field(description="Document ID to fetch chunks from.")
    chunks: list[int] = Field(
        min_length=1,
        max_length=5,
        description="Chunk indexes to fetch; select at most five chunks.",
    )


class Get(Tool, Signature):
    """Used to page through documents of interest found by search."""

    KIND = Kinds.READ

    @ccp
    def Projection(cls):
        return Projection

    @classes
    def Validators(cls):
        return [CollectionValidator]

    async def run(self) -> list:
        collection = self.toolset.collection_for(self.collection_id)
        return await collection.get_chunks(
            client=self.toolset.client,
            id=self.document_id,
            chunks=self.chunks,
        )
