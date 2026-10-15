from collections.abc import AsyncIterator
from enum import auto
from functools import cached_property
from typing import ClassVar
from uuid import uuid4

from cached_classproperty import cached_classproperty
from corio import strings
from corio.enums import MapEnum
from corio.db.search.client import Client
from pydantic import BaseModel, Field, field_validator

from corio.function import cp
from corio.hash import get_hash_readable
from xah.class_collections import classes
from xah.harness.base import Harness
from xah.toolsets.kb.db import WebPage
from xah.toolsets.kb.query import Query
from xah.toolsets.kb.history import ResearchHistory
from xah.toolsets.kb.toolset import Knowledgebase

from xah.toolsets.web.base import WebTool
from xah.toolsets.web.search import Search


class ResearchOutput(BaseModel):
    MSG_HTTPS: ClassVar[str] = "Each URL must start with https://"

    urls: list[str] = Field(description=f"Relevance-ranked URLs. {MSG_HTTPS}")
    answer: str | None = Field(
        default=None,
        description="A potential definitive answer to the research query based on the search results, if one exists.",
    )
    desc: str = Field(description="Description in a short sentence of the research so far.")

    @field_validator("urls")
    @classmethod
    def urls_use_https(cls, urls: list[str]) -> list[str]:
        for url in urls:
            if not url.startswith("https://"):
                raise ValueError(cls.MSG_HTTPS)
        return urls


class Depth(MapEnum):
    QUICK = auto(), "A quick, cursory review using 1 or 2 sets of terms."
    STANDARD = auto(), "A focused review using several sets of terms and a small set of sources."
    THOROUGH = auto(), "A detailed review using multiple refined searches and source pages."
    INTENSIVE = auto(), "A comprehensive review using extensive searches, thorough search term harvesting and refinement and source coverage."


    """Select relevant web pages for a research request."""

    instructions = strings.trim(f"""        
        ## Process
        
        Research the user's request sequentially and systematically. Do not generate or
        submit batches of speculative queries, and do not spam random/similar search terms.

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
        
        ## Requested Depth

        Follow the requested research depth. Do not perform work beyond the requested depth.
        Use the depth to determine how many search terms and sources to investigate, while still prioritising relevant, high-quality results.

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
        - Tailor your answer to the request and its depth: this can be very short for simple requests, much longer for more invovled ones.
        - Similarly, some open-ended requests - e.g. "Tell me about the East Germany" - are not amenable to a single, definitive answer. You should also omit one in such cases.        
    """)

    @cached_property
    def output(self):
        return ResearchOutput

    @classes
    def Instructions(cls):
        from xah.instructions.static import Static

        return [Static]

    @classes
    def Toolsets(cls):
        from xah.toolsets.web.toolset import Web as WebBase

        class Web(WebBase):
            @classes
            def Tools(cls):
                return [Search]

        return [Web]


class Research(WebTool):
    """Search, fetch, and index web pages for the user's research request."""

    FETCH_TIMEOUT: ClassVar[int] = 60

    depth: Depth = Field(description=Depth.descriptions)

    prompt: str = Field(
        description="Research request, including detailed instructions for what to investigate."
    )

    id: str | None = Field(
        default=None,
        description="Collection ID. Leave empty for entirely new research, or provide an existing ID to extend existing research.",
    )

    def model_post_init(self, __context) -> None:
        if self.id is None:
            self.id = get_hash_readable(str(uuid4()), length=4)

    @cached_property
    def knowledgebase(self):
        from xah.toolsets.kb.toolset import Knowledgebase

        return self.ctx.deps.toolsets.name[Knowledgebase.name]

    @cached_property
    def client(self) -> Client:
        return self.knowledgebase.client

    @cached_property
    def harness(self):
        harness = HarnessResearch.from_parent(self.ctx.deps)
        return harness

    @cp
    def history_entry(self):
        return self.knowledgebase.history.id.get(self.id)

    @cp
    def requested_depth_section(self) -> str:
        return strings.trim(
            f"""
            # Requested Depth {self.depth}

            {self.depth.description}
            """
        )

    @cp
    def historical_prompt_section(self) -> str:
        if self.history_entry is None:
            return ""

        prompts = "\n".join(f"- {prompt}" for prompt in self.history_entry.prompts)
        return strings.trim(
            f"""
            # Historical prompts
            {prompts}
            """
        )

    @cp
    def current_prompt_section(self) -> str:
        return strings.trim(
            f"""
            # Latest/current prompt
            {self.prompt}
            """
        )

    @cp
    def request(self) -> str:
        return strings.trim(
            self.requested_depth_section,
            self.historical_prompt_section,
            self.current_prompt_section,
        )

    async def run(self) -> ResearchOutput:
        result = await self.harness.agent.run(self.request, deps=self.harness.deps)
        if self.history_entry is None:
            history_entry = ResearchHistory.Prompts(
                id=self.id,
                desc=result.output.desc,
                prompts=[self.prompt],
            )
            self.knowledgebase.history.append(history_entry)
        else:
            self.history_entry.prompts.append(self.prompt)
            self.history_entry.desc = result.output.desc
        urls = result.output.urls
        if self.depth in {Depth.QUICK, Depth.STANDARD}:
            return result.output

        fetch_results = [result async for result in super().fetch(urls)]
        documents = [
            WebPage(
                id=get_hash_readable(result.url + result.text, length=8),
                collection_id=self.id,
                title=result.title,
                url=result.url,
                text=result.text,
            )
            for result in fetch_results
            if result.succeeded
        ]
        if not documents:
            return result.output

        await WebPage.build(
            data=documents,
            client=self.client,
        )

        feedback = f"""
            The research tool has provided a provisional answer, based on summaries only.
            A research knowledgebase has also been compiled for this question, containing the full sources, so you can perform deeper research yourself.
            Use the {Knowledgebase.name} tools with Collection ID `{self.id}` to query and page through its contents.
            """
        self.feedback(feedback)

        return result.output

    async def fetch(self, urls: list[str]) -> AsyncIterator[WebPage]:
        async for result in super().fetch(urls):
            if not result.succeeded:
                continue
            yield WebPage(
                id=get_hash_readable(result.url + result.text, length=8),
                collection_id=self.id,
                title=result.title,
                url=result.url,
                text=result.text,
            )
