import asyncio
import re
from collections.abc import AsyncIterator
from functools import cached_property
from typing import ClassVar, Never

from corio import Constants
from corio.logs import logger
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
    DefaultMarkdownGenerator,
    PruningContentFilter,
)
from crawl4ai.antibot_detector import is_blocked
from pydantic import BaseModel
from pydantic_ai import ToolFailed

from xah.toolsets.base.tool import Tool


class FetchResult(BaseModel):
    """The readable result or failure explanation for one URL."""

    url: str
    title: str | None = None
    text: str | None = None
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


class WebTool(Tool):
    FETCH_TIMEOUT: ClassVar[int] = 60

    @cached_property
    def client(self):
        return self.toolset.client

    @cached_property
    def browser(self) -> BrowserConfig:
        return BrowserConfig(headless=True)

    @cached_property
    def generator(self) -> DefaultMarkdownGenerator:
        return DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.6)
        )

    @cached_property
    def config(self) -> CrawlerRunConfig:
        return CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            markdown_generator=self.generator,
            page_timeout=self.FETCH_TIMEOUT * 1000,
            wait_for_timeout=self.FETCH_TIMEOUT * 1000,
            max_retries=0,
        )

    async def fetch_url(self, crawler, url) -> FetchResult:
        try:
            async with asyncio.timeout(self.FETCH_TIMEOUT):
                result = await crawler.arun(url, config=self.config)
        except TimeoutError:
            return FetchResult(url=url, error="The request timed out.")
        except Exception as error:
            return FetchResult(url=url, error=str(error))

        if not result.success:
            error = result.error_message or "The page could not be fetched."
            return FetchResult(url=url, error=error)

        blocked, reason = is_blocked(
            result.status_code,
            result.html,
            result.error_message,
        )
        if blocked:
            return FetchResult(url=url, error=reason or "The page was blocked by anti-bot protection.")

        markdown = result.markdown.fit_markdown or result.markdown.raw_markdown
        text = re.sub(r"\n{3,}", "\n\n", markdown).strip()
        if not text:
            return FetchResult(url=url, error="The page contained no readable text.")

        title = result.metadata.get("title") or url or Constants.PROMPT_NONE_SPECIFIED
        return FetchResult(url=url, title=title, text=text)

    async def fetch(self, urls: list[str]) -> AsyncIterator[FetchResult]:
        async with AsyncWebCrawler(config=self.browser) as crawler:
            results = await asyncio.gather(
                *(self.fetch_url(crawler, url) for url in urls)
            )

        for result in results:
            yield result

    def fail(self, error: Exception) -> Never:
        tool_name = self.toolset.tool_name(type(self))
        logger.warning(f"{tool_name} failed: {error}")
        message = f"The web request failed: {error}. The web service may be temporarily unavailable."
        raise ToolFailed(message) from error
