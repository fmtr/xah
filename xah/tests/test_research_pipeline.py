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
from xah.toolsets.web import research as research_module
from xah.toolsets.web.research import Research, ResearchOutput
from xah.toolsets.web.toolset import Web


class FakeEmbedder:
    batch_size = 32
    config = {
        "vectors_config": {
            "dense": models.VectorParams(size=2, distance=models.Distance.COSINE),
            "multi": models.VectorParams(
                size=2,
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
                dense=[1.0, 0.0],
                multi=[[1.0, 0.0]],
            )
        return batch

    async def add_vectors(self, points):
        return self._add_vectors(points)

    def _add_vectors(self, points):
        points = list(points)
        self.embed(points)
        yield from points


def test_research_output_describes_urls_and_answer():
    assert set(ResearchOutput.model_fields) == {"urls", "answer"}
    assert ResearchOutput.model_fields["urls"].description == (
        "Relevance-ranked URLs. Each URL must start with https://"
    )
    assert ResearchOutput.model_fields["answer"].description == (
        "A potential answer to the research query based on the search results."
    )
    assert ResearchOutput(urls=["https://example.com"]).answer is None


def test_research_output_rejects_non_https_urls():
    with pytest.raises(ValueError, match="Each URL must start with https://"):
        ResearchOutput(urls=["http://example.com"])


def test_research_id_is_generated_or_preserved():
    assert Research.model_construct(research_id=None).research_id
    assert Research.model_construct(research_id="research-1").research_id == "research-1"
    assert Research.model_fields["research_id"].description == (
        "Leave empty for entirely new research, or provide an existing research id "
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

    monkeypatch.setattr(research_module, "AsyncWebCrawler", Crawler)
    research = Research.model_construct(research_id="research-1")

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

    monkeypatch.setattr(research_module, "AsyncWebCrawler", Crawler)
    research = Research.model_construct(research_id="research-1")

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

    monkeypatch.setattr(research_module, "AsyncWebCrawler", Crawler)
    monkeypatch.setattr(Research, "FETCH_TIMEOUT", 0.01)
    research = Research.model_construct(research_id="research-1")

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
    knowledgebase = SimpleNamespace(client=client, name=Knowledgebase.name)
    deps = SimpleNamespace(toolsets=SimpleNamespace(name={Knowledgebase.name: knowledgebase}))
    context = RunContext(
        deps=deps,
        model=None,
        usage=RunUsage(),
        pending_messages=[],
    )
    web = Web()
    research = Research(ctx=context, toolset=web, prompt="question")
    captured = {}

    class Agent:
        async def run(self, prompt, deps):
            return SimpleNamespace(output=ResearchOutput(urls=["https://example.com"]))

    class Harness:
        agent = Agent()
        deps = object()

        @classmethod
        def from_parent(cls, parent):
            return cls()

    async def fetch(self, urls):
        yield SimpleNamespace(url=urls[0])

    def build(cls, *, data, client):
        captured["data"] = data
        captured["client"] = client

    monkeypatch.setattr(research_module, "HarnessResearch", Harness)
    monkeypatch.setattr(Research, "fetch", fetch)
    monkeypatch.setattr(WebPage, "build", classmethod(build))

    await research.run()

    assert captured["client"] is client


@pytest.mark.asyncio
async def test_research_documents_are_inserted_indexed_and_queryable(knowledgebase):
    document = WebPage(
        id="page-1",
        research_id="research-1",
        title="Meteors",
        url="https://example.com/meteors",
        text="Historical observations of meteors.",
    )

    WebPage.build(data=[document], client=knowledgebase.client)

    collection = knowledgebase.client.get_collection(collection_name=WebPage.name)
    assert collection.status == models.CollectionStatus.GREEN
    assert knowledgebase.client.collection_exists(collection_name=WebPage.name)

    context = RunContext(
        deps=SimpleNamespace(toolsets=[knowledgebase]),
        model=None,
        usage=RunUsage(),
    )
    result = await Query(
        ctx=context,
        toolset=knowledgebase,
        query="meteors",
        research_id="research-1",
    ).run()

    assert [hit.url for hit in result] == [document.url]
    assert result[0].research_id == document.research_id
