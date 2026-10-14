from pydantic import Field

from xah.toolsets.web.base import FetchResult, WebTool


class Fetch(WebTool):
    """Fetch web pages and return their readable text."""

    urls: list[str] = Field(description="The web page URLs to fetch.")

    async def run(self) -> list[FetchResult]:
        results = [result async for result in self.fetch(self.urls)]
        return results
