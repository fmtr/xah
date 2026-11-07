from typing import Annotated

from pydantic import Field

from corio import strings

from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.output import Output
from xah.toolsets.base.tool import Input as InputBase, Kinds
from xah.toolsets.web.base import FetchResult, WebTool


class FetchOutput(Output):
    results: list[FetchResult]

    def get_agent(self) -> list[dict]:
        return self.model_dump(mode="json")["results"]


class Input(InputBase):
    urls: Annotated[list[str], Field(min_length=1, description="One or more web page URLs to fetch.")]

    def get_projection(self, request):
        if len(self.urls) == 1:
            title = f"Fetching {self.preview(self.urls[0], limit=80)}"
        else:
            title = f"Fetching {len(self.urls)} URLs"
        return AcpToolProjection(
            content=[self.content_block(strings.join(self.urls, sep="\n"))],
            title=title,
        )


class Fetch(WebTool, Input):
    """Fetch web pages and return their readable text."""

    KIND = Kinds.FETCH

    async def run(self) -> FetchOutput:
        results = [result async for result in self.fetch(self.urls)]
        return FetchOutput(results=results)
