import asyncio
import re
from collections.abc import AsyncIterator
from functools import cached_property
from uuid import uuid4

from cached_classproperty import cached_classproperty
from corio import strings
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from pydantic import Field

from xah.class_collections import ClassDeclaration
from xah.harness.base import HarnessAgent
from xah.toolsets.base.tool import Tool
from xah.toolsets.kb.db import WebPage
from xah.toolsets.kb.query import Query

from xah.toolsets.web.search import Search


class HarnessResearch(HarnessAgent):
    """Select relevant web pages for a research request."""

    instructions = strings.trim("""
        Turn the user's research request into several traditional web search queries.
        Use different phrasings and angles so the results cover the subject broadly.
        Return a relevance-ranked shortlist containing only URLs. Do not return prose,
        explanations, titles, or search result objects.
    """)

    @cached_property
    def output(self):
        return list[str]

    @cached_classproperty
    def TOOLSETS(cls):
        from xah.toolsets.web.toolset import Web as WebBase

        class Web(WebBase):
            @cached_classproperty
            def TOOLS(cls):
                return ClassDeclaration(remove=ClassDeclaration.all, add=[Search])

        return [Web]


class Research(Tool):
    """Search, fetch, and index web pages for the user's research request."""

    prompt: str = Field(
        description="Research request, including detailed instructions for what to investigate."
    )

    @cached_property
    def research_id(self) -> str:
        return str(uuid4())

    async def run(self) -> str:
        from xah.toolsets.kb.toolset import Knowledgebase


        harness = HarnessResearch.from_parent(self.ctx.deps)
        urls = (await harness.agent.run(self.prompt, deps=harness.deps)).output
        documents = [page async for page in self.fetch(urls)]
        client=self.ctx.deps.toolsets.name[Knowledgebase.name].client
        WebPage.build(data=documents, client=client)
        query_tool = self.toolset.tool_name(Query)
        return strings.trim(
            f"""
            Research is ready under research_id `{self.research_id}`.
            Use the knowledgebase toolset's `{query_tool}` tool with this research_id
            to query the indexed pages and continue the investigation.
            """
        )

    async def fetch(self, urls: list[str]) -> AsyncIterator[WebPage]:
        browser_config = BrowserConfig(headless=True)
        run_config = CrawlerRunConfig()
        async with AsyncWebCrawler(config=browser_config) as crawler:
            results = await asyncio.gather(
                *(crawler.arun(url, config=run_config) for url in urls)
            )

        for url, result in zip(urls, results):
            if not result.success:
                continue
            markdown = result.markdown.fit_markdown or result.markdown.raw_markdown
            text = re.sub(r"\n{3,}", "\n\n", markdown).strip()
            if not text:
                continue
            title = result.metadata.get("title", url)
            yield WebPage(
                id=url,
                research_id=self.research_id,
                title=title,
                url=url,
                text=text,
            )
