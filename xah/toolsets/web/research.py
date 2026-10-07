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
from xah.toolsets.kb.toolset import Knowledgebase

from xah.toolsets.web.search import Search


class ResearchOutput(BaseModel):
    MSG_HTTPS: ClassVar[str]="Each URL must start with https://"

    urls: list[str] = Field(
        description=f"Relevance-ranked URLs. {MSG_HTTPS}"
    )
    answer: str | None = Field(
        default=None,
        description="A potential definitive answer to the research query based on the search results, if one exists.",
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
        - Search output contains excerpts only, not full pages. A URL will contain more content than its excerpt, so choose sources accordingly.
        
        ### Avoid

        - Landing pages that do not contain the relevant material.
        - Search-result pages, link farms, link lists, and directories whose useful
          content requires further navigation.
        - Paywalls, login-gated pages, and sources that cannot be fetched or read.
        - Duplicates, near-duplicates, syndicated copies, and pages with little
          substantive content.
        - Search queries assembled from unsupported guesses or an unstructured list of
          synonyms.
          
        ## Output
        
        Return a relevance-ranked shortlist of URLs and, when supported by high-quality
        search material, a potential answer. Do not return search queries, explanations,
        titles, citations, or search-result objects.

        ## Answer

        - The results of each search provides an extra field with a ready-made answer to its query.
        - When providing your own answer, synthesize it from the highest-quality information available in:
            - The answer fields from each search.
            - The contents of the search excerpts.        
        - If the aggregated sources do not contain a good-quality answer, you may choose not to provide one.
        - Similarly, some open-ended requests - e.g. "Tell me about the East Germany" - are not amenable to a single, definitive answer. You should also omit one in such cases.

        
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

    research_id: str | None = Field(
        default=None,
        description="Leave empty for entirely new research, or provide an existing ID to extend existing research.",
    )

    def model_post_init(self, __context) -> None:
        if self.research_id is None:
            self.research_id = get_hash_readable(str(uuid4()), length=4)

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
        )

    async def run(self) -> str:

        result=await self.harness.agent.run(self.prompt, deps=self.harness.deps)
        urls = result.output.urls
        answer= result.output.answer
        documents = [page async for page in self.fetch(urls)]

        await WebPage.build(
            data=documents,
            client=self.client,
        )

        self.feedback(
            f"""
            The research knowledgebase has been compiled for this question, so you can perform deeper research yourself.
            Use the {Knowledgebase.name} tools with research_id `{self.research_id}` to query and page through its contents.
            """
        )

        text = strings.trim(
            f"""
            Research completed. The research is ready under research_id `{self.research_id}`.

            # Provisional Answer
            """,
            answer,
        )

        return text

    async def fetch(self, urls: list[str]) -> AsyncIterator[WebPage]:
        async with AsyncWebCrawler(config=self.browser) as crawler:
            results = await asyncio.gather(
                *(crawler.arun(url, config=self.config) for url in urls)
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
