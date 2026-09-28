from corio import yml
from xah.toolsets.base.tool import Tool


class List(Tool):
    """List the document types available in the knowledgebase."""

    async def run(self) -> str:
        documents = {document.name: document.description for document in self.toolset.DOCUMENTS}
        return yml.to_yaml(documents)
