from typing import Annotated

from pydantic import Field

from corio import Constants, strings

from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.output import Output
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds
from xah.toolsets.web.base import FetchResult, WebTool


class FetchOutput(Output):
    results: list[FetchResult]

    @property
    def agent(self) -> list[dict]:
        return self.model_dump(mode="json")["results"]

    @property
    def title(self) -> str:
        page_count = strings.suffix_plural(len(self.results), "page")
        return f"{self.request.input.title} {Constants.ARROW_RIGHT} {page_count}"

    @property
    def projection(self):
        content = []
        for result in self.results:
            title = result.title or result.url
            if result.succeeded:
                page = strings.trim(f"## {title}", result.text)
                content.append(self.content_block(page))
                content.append(
                    self.resource_link_content(
                        result.url,
                        name=title,
                        title=title,
                    )
                )
                continue

            content.append(self.content_block(f"Could not fetch {result.url}: {result.error}"))

        return AcpToolProjection(
            content=content,
            title=self.title,
            status=self.request.status,
        )


class Input(InputBase):
    urls: Annotated[list[str], Field(min_length=1, description="One or more web page URLs to fetch.")]

    @property
    def title(self):
        urls = strings.join_natural(self.urls, mask="`{}`")
        return f"Fetching {urls}"

    @property
    def projection(self):
        return AcpToolProjection(
            content=[self.content_block(strings.join(self.urls, sep="\n"))],
            title=self.title,
        )


class Fetch(WebTool, Input):
    """Fetch web pages and return their readable text."""

    KIND = Kinds.FETCH

    async def run(self) -> FetchOutput:
        results = [result async for result in self.fetch(self.urls)]
        return FetchOutput(results=results)
