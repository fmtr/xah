from typing import Any

from pydantic import BaseModel, Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.output import Output
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds
from xah.toolsets.web.base import WebTool


class WebSearchResult(BaseModel):
    title: str | None = None
    url: str
    content: str | None = None
    score: float | None = None
    raw_content: str | None = None


class WebSearchOutput(Output):
    query: str | None = None
    answer: str | None = None
    results: list[WebSearchResult]

    @property
    def agent(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class Input(InputBase):
    query: str = Field(description="Web search query.")

    @property
    def title(self):
        return f"Searching the web for `{self.preview(self.query, limit=20)}`"

    @property
    def projection(self):
        return AcpToolProjection(
            content=[self.content_block(f"Query: {self.query}")],
            title=self.title,
        )


class Search(WebTool, Input):
    """Search the web and return relevant sources and an answer."""

    KIND = Kinds.SEARCH

    async def run(self) -> WebSearchOutput:
        try:
            result = await self.client.search(
                query=self.query,
                search_depth="advanced",
                topic="general",
                max_results=5,
                include_answer="advanced",
                include_raw_content=False,
                include_images=False,
            )
            return WebSearchOutput.model_validate(result)
        except Exception as error:
            self.fail(error)
