from typing import Annotated

from pydantic import Field

from corio import strings

from corio.function import ccp
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase
from xah.toolsets.web.base import FetchResult, WebProjection, WebTool


class Projection(WebProjection):
    def start(self):
        urls = self.sig.urls
        if len(urls) == 1:
            title = f"Fetching {self.preview(urls[0], limit=80)}"
        else:
            title = f"Fetching {len(urls)} URLs"
        return AcpToolProjection(
            content=[self.content(strings.join(urls, sep="\n"))],
            title=title,
        )


class Signature(SignatureBase):
    urls: Annotated[list[str], Field(min_length=1, description="One or more web page URLs to fetch.")]


class Fetch(WebTool, Signature):
    """Fetch web pages and return their readable text."""

    KIND = Kinds.FETCH

    @ccp
    def Projection(cls):
        return Projection

    async def run(self) -> list[FetchResult]:
        results = [result async for result in self.fetch(self.urls)]
        return results
