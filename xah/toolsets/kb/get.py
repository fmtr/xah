from pydantic import Field

from corio import yml
from corio.iterator import ilist
from xah.toolsets.base.tool import Tool


class Get(Tool):
    """Fetch a complete document from the knowledgebase by ID."""

    doc_type: str = Field(description="Document type name from the knowledgebase.")
    id: str = Field(description="Document ID to fetch.")

    async def run(self) -> str:
        documents = ilist(self.toolset.DOCUMENTS)
        document = documents.name[self.doc_type]
        result = document.get(client=self.toolset.client, id=self.id)
        return yml.to_yaml(result.model_dump())
