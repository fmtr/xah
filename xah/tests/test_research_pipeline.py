import asyncio
from types import SimpleNamespace

import pytest
from pydantic_ai import RunContext
from pydantic_ai.usage import RunUsage
from qdrant_client.http import models

from corio.db.search.client import Client
from corio.db.search.embedder import Vectors
from xah.toolsets.kb.db import WebPage
from xah.toolsets.kb.query import Query
from xah.toolsets.kb.toolset import Knowledgebase
from xah.toolsets.web import base as web_base
from xah.toolsets.web.base import FetchResult, WebTool
from xah.toolsets.web.research import Depth, Research, ResearchOutput
from xah.toolsets.web.toolset import Web


class FakeEmbedder:
    batch_size = 32
    config = {
        "vectors_config": {
            "dense": models.VectorParams(size=1024, distance=models.Distance.COSINE),
            "multi": models.VectorParams(
                size=1024,
                distance=models.Distance.COSINE,
                multivector_config=models.MultiVectorConfig(
                    comparator=models.MultiVectorComparator.MAX_SIM,
                ),
            ),
        },
        "sparse_vectors_config": {
            "sparse": models.SparseVectorParams(),
            "simple": models.SparseVectorParams(),
        },
    }

    def embed(self, batch):
        for query in batch:
            query.vectors = Vectors(
                simple=models.SparseVector(indices=[1], values=[1.0]),
                sparse=models.SparseVector(indices=[1], values=[1.0]),
                dense=[1.0] + [0.0] * 1023,
                multi=[[1.0] + [0.0] * 1023],
            )
        return batch

    async def add_vectors(self, points):
        return self._add_vectors(points)

    def _add_vectors(self, points):
        points = list(points)
        self.embed(points)
        return points


def test_research_output_describes_urls_and_answer():
    assert set(ResearchOutput.model_fields) == {"urls", "answer", "desc"}
    assert ResearchOutput.model_fields["urls"].description == (
        "Relevance-ranked URLs. Each URL must start with https://"
    )
    assert ResearchOutput.model_fields["answer"].description == (
        "A potential definitive answer to the research query based on the search results, if one exists."
    )
    assert ResearchOutput.model_fields["desc"].description == (
        "Description in a short sentence of the research so far."
    )
    assert ResearchOutput(urls=["https://example.com"], desc="Initial research").answer is None


def test_research_output_rejects_non_https_urls():
    with pytest.raises(ValueError, match="Each URL must start with https://"):
        ResearchOutput(urls=["http://example.com"])


def test_research_id_is_generated_or_preserved():
    context = RunContext(deps=SimpleNamespace(), model=None, usage=RunUsage())
    generated = Research(
        ctx=context,
        toolset=Web(),
        prompt="question",
        depth=Depth.QUICK,
    )
    preserved = Research(
        ctx=context,
        toolset=Web(),
        prompt="question",
        depth=Depth.QUICK,
        id="research-1",
    )

    assert generated.id
    assert preserved.id == "research-1"
    assert Research.model_fields["id"].description == (
        "Collection ID. Leave empty for entirely new research, or provide an existing ID "
        "to extend existing research."
    )


@pytest.mark.asyncio
async def test_fetch_indexes_raw_markdown_when_fit_markdown_is_empty(monkeypatch):
    class Crawler:
        def __init__(self, config):
            self.config = config

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def arun(self, url, config):
            return SimpleNamespace(
                success=True,
                html="<html><body><p>" + ("Meteor observations. " * 100) + "</p></body></html>",
                status_code=200,
                error_message=None,
                markdown=SimpleNamespace(fit_markdown="", raw_markdown="# Meteor"),
                metadata={"title": None},
            )

    monkeypatch.setattr(web_base, "AsyncWebCrawler", Crawler)
    research = Research.model_construct(id="research-1")

    pages = [page async for page in research.fetch(["https://example.com"])]

    assert len(pages) == 1
    assert pages[0].text == "# Meteor"
    assert pages[0].title == "https://example.com"


@pytest.mark.asyncio
async def test_fetch_skips_anti_bot_pages(monkeypatch):
    class Crawler:
        def __init__(self, config):
            self.config = config

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def arun(self, url, config):
            return SimpleNamespace(
                success=True,
                html="<html><body>Access denied</body></html>",
                status_code=503,
                error_message="Blocked by anti-bot protection: HTTP 503 with HTML content",
                markdown=SimpleNamespace(
                    fit_markdown="Access denied",
                    raw_markdown="Access denied",
                ),
                metadata={"title": None},
            )

    monkeypatch.setattr(web_base, "AsyncWebCrawler", Crawler)
    research = Research.model_construct(id="research-1")

    pages = [page async for page in research.fetch(["https://example.com"])]

    assert pages == []


@pytest.mark.asyncio
async def test_fetch_skips_timed_out_urls(monkeypatch):
    class Crawler:
        def __init__(self, config):
            self.config = config

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def arun(self, url, config):
            await asyncio.sleep(1)

    monkeypatch.setattr(web_base, "AsyncWebCrawler", Crawler)
    monkeypatch.setattr(Research, "FETCH_TIMEOUT", 0.01)
    research = Research.model_construct(id="research-1")

    pages = [page async for page in research.fetch(["https://example.com"])]

    assert pages == []


@pytest.fixture
def knowledgebase(monkeypatch):
    embedder = FakeEmbedder()
    monkeypatch.setattr(WebPage, "embedder", embedder)
    toolset = Knowledgebase()
    toolset.client = Client(location=Client.MEMORY)
    return toolset


@pytest.mark.asyncio
async def test_research_indexes_with_parent_knowledgebase_client(monkeypatch):
    client = object()
    knowledgebase = SimpleNamespace(
        client=client,
        name=Knowledgebase.name,
        history=SimpleNamespace(id={}, append=lambda entry: None),
    )
    deps = SimpleNamespace(
        toolsets=SimpleNamespace(all=SimpleNamespace(name={Knowledgebase.name: knowledgebase}))
    )
    context = RunContext(
        deps=deps,
        model=None,
        usage=RunUsage(),
        pending_messages=[],
    )
    web = Web()
    research = Research(
        ctx=context,
        toolset=web,
        prompt="question",
        depth=Depth.THOROUGH,
    )
    captured = {}

    class Agent:
        async def run(self, prompt, deps):
            captured["prompt"] = prompt
            return SimpleNamespace(
                output=ResearchOutput(
                    urls=["https://example.com"],
                    desc="Initial research",
                )
            )

    class Harness:
        agent = Agent()
        deps = object()

        @classmethod
        def from_parent(cls, parent):
            return cls()

    async def fetch(self, urls):
        yield FetchResult(
            url=urls[0],
            title="Example",
            text="Research text",
        )

    async def build(cls, *, data, client):
        captured["data"] = data
        captured["client"] = client

    monkeypatch.setattr(Research, "Harness", Harness)
    monkeypatch.setattr(WebTool, "fetch", fetch)
    monkeypatch.setattr(WebPage, "build", classmethod(build))

    await research.run()

    assert captured["client"] is client
    assert captured["prompt"] == (
        "# Requested Depth THOROUGH\n\n"
        "A detailed review using multiple refined searches and source pages.\n\n"
        "# Latest/current prompt\nquestion"
    )


@pytest.mark.asyncio
async def test_research_returns_initial_results_when_all_fetches_fail(monkeypatch):
    knowledgebase = SimpleNamespace(
        client=object(),
        name=Knowledgebase.name,
        history=SimpleNamespace(id={}, append=lambda entry: None),
    )
    context = RunContext(
        deps=SimpleNamespace(
            toolsets=SimpleNamespace(
                all=SimpleNamespace(name={Knowledgebase.name: knowledgebase})
            )
        ),
        model=None,
        usage=RunUsage(),
    )
    research = Research(
        ctx=context,
        toolset=Web(),
        prompt="question",
        depth=Depth.THOROUGH,
    )
    output = ResearchOutput(urls=["https://example.com"], desc="Initial research")

    class Agent:
        async def run(self, prompt, deps):
            return SimpleNamespace(output=output)

    class Harness:
        agent = Agent()
        deps = object()

        @classmethod
        def from_parent(cls, parent):
            return cls()

    async def fetch(self, urls):
        yield FetchResult(url=urls[0], error="The request timed out.")

    monkeypatch.setattr(Research, "Harness", Harness)
    monkeypatch.setattr(WebTool, "fetch", fetch)

    assert await research.run() is output


@pytest.mark.asyncio
async def test_research_documents_are_inserted_indexed_and_queryable(knowledgebase):
    document = WebPage(
        id="page-1",
        collection_id="research-1",
        title="Meteors",
        url="https://example.com/meteors",
        text="Historical observations of meteors.",
    )

    await WebPage.build(data=[document], client=knowledgebase.client)

    collection = await knowledgebase.client.get_collection(collection_name=WebPage.name)
    assert collection.status == models.CollectionStatus.GREEN
    assert await knowledgebase.client.collection_exists(collection_name=WebPage.name)

    context = RunContext(
        deps=SimpleNamespace(toolsets=[knowledgebase]),
        model=None,
        usage=RunUsage(),
        pending_messages=[],
    )
    result = await Query(
        ctx=context,
        toolset=knowledgebase,
        query="meteors",
        collection_id="research-1",
    ).run()

    assert [hit.url for hit in result] == [document.url]
    assert result[0].collection_id == document.collection_id
