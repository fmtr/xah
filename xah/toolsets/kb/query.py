from pydantic import Field

from corio import strings, yml

from xah.toolsets.base.tool import Tool


class Query(Tool):
    """Run a text query against a knowledgebase document type."""

    query: str = Field(
        description=strings.trim("""
        Text query to run against the document type.
        Note that this is a **semantic** search, not keyword.
        Stuffing the query with many semantically-similar keywords will not perform well.
        """)
    )

    async def run(self) -> str:
        from xah.toolsets.kb.get import Get

        document = self.toolset.DOCUMENT
        results = next(document.query(texts=[self.query], client=self.toolset.client))
        hits = [hit.model_dump() for hit in results.hits]
        yaml_results = yml.to_yaml(hits)
        get_tool_name = self.toolset.tool_name(Get)
        text = strings.trim(
            yaml_results,
            f"""
            Note: These are **excerpts only** from the matching documents.
            Full documents should be fetched using the `{get_tool_name}` tool.
            """
        )
        return text
