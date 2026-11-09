from typing import Annotated

from pydantic import Field

from corio import strings

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
    def content(self):
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

        return content


class Input(InputBase):
    urls: Annotated[list[str], Field(min_length=1, description="One or more web page URLs to fetch.")]

    @property
    def title(self):
        if len(self.urls) == 1:
            return f"Fetching `{self.urls[0]}`"
        return f"Fetching {len(self.urls)} URLs"

    @property
    def content(self):
        return [self.content_block(strings.join(self.urls, sep="\n"))]


class Fetch(WebTool, Input):
    """Fetch web pages and return their readable text."""

    KIND = Kinds.FETCH

    async def run(self) -> FetchOutput:
        results = [result async for result in self.fetch(self.urls)]
        return FetchOutput(results=results)
