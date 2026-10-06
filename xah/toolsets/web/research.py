import asyncio
import re
from collections.abc import AsyncIterator
from functools import cached_property
from typing import ClassVar
from uuid import uuid4

from cached_classproperty import cached_classproperty
from corio import strings
from corio.db.search.client import Client
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, DefaultMarkdownGenerator, PruningContentFilter, \
    CacheMode
from pydantic import BaseModel, Field, field_validator

from corio.hash import get_hash_readable
from xah.class_collections import ClassDeclaration
from xah.harness.base import HarnessAgent
from xah.toolsets.base.tool import Tool
from xah.toolsets.kb.db import WebPage
from xah.toolsets.kb.query import Query

from xah.toolsets.web.search import Search


class ResearchOutput(BaseModel):
    MSG_HTTPS: ClassVar[str]="Each URL must start with https://"

    urls: list[str] = Field(
        description=f"Relevance-ranked URLs. {MSG_HTTPS}"
    )

    @field_validator("urls")
    @classmethod
    def urls_use_https(cls, urls: list[str]) -> list[str]:
        for url in urls:
            if not url.startswith("https://"):
                raise ValueError(cls.MSG_HTTPS)
        return urls


class HarnessResearch(HarnessAgent):
    """Select relevant web pages for a research request."""

    instructions = strings.trim("""
        Research the user's request sequentially and systematically. Do not generate or
        submit a batch of speculative queries, and do not spam random search terms.

        ## Process

        - Translate the request into an initial, focused search query that captures the
          subject, timeframe, geography, perspective, or other constraints that matter.
        - Run exactly **one search query at a time**.
        - Assess the quality of the returned results before searching again: check whether
          they are relevant to the request, specific enough to answer it, and likely to
          lead to useful, readable source pages.
        - Harvest useful terminology from the results, including names, alternate
          spellings, technical terms, dates, places, organisations, and distinctive
          phrases.
        - Use those discoveries to refine the next query. Change the wording or angle
          deliberately rather than repeating an equivalent query.
        - Repeat this assess, harvest, and refine cycle one query at a time until the
          search terms are strong and the results provide good coverage of the request.
        - Prefer queries that investigate different meaningful aspects of the request,
          rather than queries that differ only cosmetically.
        - Keep track of promising pages across searches and remove duplicate URLs.

        ## Choose Suitable Pages

        - Select pages that are likely to contain the requested information directly and
          can be read by an agent without further navigation.
        - Prefer substantive primary sources, official publications, reputable reference
          works, and well-supported specialist sources when they are available.
        - Prefer pages with clear, accessible text over pages whose useful content is
          mainly embedded in images, video, interactive widgets, or downloadable files.
        - Choose a small, relevant set of complementary pages rather than every plausible
          result; coverage and source quality matter more than quantity.
        - Include sources that directly address the request, not merely pages that mention
          its keywords.

        ## Avoid

        - Landing pages that do not contain the relevant material.
        - Search-result pages, link farms, link lists, and directories whose useful
          content requires further navigation.
        - Paywalls, login-gated pages, and sources that cannot be fetched or read.
        - Duplicates, near-duplicates, syndicated copies, and pages with little
          substantive content.
        - Search queries assembled from unsupported guesses or an unstructured list of
          synonyms.

        Return a relevance-ranked shortlist containing only URLs. Do not return search
        queries, prose, explanations, titles, citations, or search-result objects.
    """)

    @cached_property
    def output(self):
        return ResearchOutput

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
        return get_hash_readable(str(uuid4()),length=4)

    @cached_property
    def client(self) -> Client:
        """

        Fetch the DB client from the KB toolset

        """
        from xah.toolsets.kb.toolset import Knowledgebase

        client = self.ctx.deps.toolsets.name[Knowledgebase.name].client
        return client

    @cached_property
    def harness(self):
        harness = HarnessResearch.from_parent(self.ctx.deps)
        return harness

    async def run(self) -> str:

        result=await self.harness.agent.run(self.prompt, deps=self.harness.deps)
        urls = result.output.urls
        documents = [page async for page in self.fetch(urls)]

        WebPage.build(data=documents, client=self.client)
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
        md_generator = DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(threshold=0.6)
        )

        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            markdown_generator=md_generator
        )
        async with AsyncWebCrawler(config=browser_config) as crawler:
            results = await asyncio.gather(
                *(crawler.arun(url, config=config) for url in urls)
            )

        for url, result in zip(urls, results):
            if not result.success:
                continue
            md_fit=result.markdown.fit_markdown
            md_raw=result.markdown.raw_markdown
            markdown = md_fit or md_raw
            text = re.sub(r"\n{3,}", "\n\n", markdown).strip()
            if not text:
                continue
            title = result.metadata.get("title", url)
            yield WebPage(
                id=get_hash_readable(url+text,length=8),
                research_id=self.research_id,
                title=title,
                url=url,
                text=text,
            )
