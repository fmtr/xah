from pydantic import Field

from xah.toolsets.web.base import WebTool


class Search(WebTool):
    """Search the web and return relevant sources and an answer."""

    query: str = Field(description="Web search query.")

    async def run(self) -> dict:
        try:
            return await self.client.search(
                query=self.query,
                search_depth="advanced",
                topic="general",
                max_results=5,
                include_answer="advanced",
                include_raw_content=False,
                include_images=False,
            )
        except Exception as error:
            self.fail(error)
