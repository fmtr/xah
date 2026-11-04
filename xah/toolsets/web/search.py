from pydantic import Field

from corio.function import ccp
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase
from xah.toolsets.web.base import WebProjection, WebTool


class Projection(WebProjection):
    def start(self):
        query = self.sig.query
        return AcpToolProjection(
            content=[self.content(f"Query: {query}")],
            title=f"Search web for {self.preview(query, limit=80)}",
        )


class Signature(SignatureBase):
    query: str = Field(description="Web search query.")


class Search(WebTool, Signature):
    """Search the web and return relevant sources and an answer."""

    KIND = Kinds.SEARCH

    @ccp
    def Projection(cls):
        return Projection

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
