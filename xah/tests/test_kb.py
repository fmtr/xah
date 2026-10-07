from types import SimpleNamespace

import pytest
import pytest_asyncio
from pydantic_ai import RunContext, ToolFailed
from pydantic_ai.usage import RunUsage
from qdrant_client.http import models

from corio.db.search.client import Client
from corio.db.search.query import Query as SearchQuery
from corio.hash import get_hash_int

from xah.toolsets.kb.db import WebPage, WebPageBuilder
from xah.toolsets.kb.get import Get
from xah.toolsets.kb.query import Query
from xah.toolsets.kb.toolset import Knowledgebase


@pytest.fixture
def kb():
    toolset = Knowledgebase()
    ctx = RunContext(deps=SimpleNamespace(toolsets=[toolset]), model=None, usage=RunUsage())
    return toolset, ctx


@pytest_asyncio.fixture
async def knowledgebase():
    toolset = Knowledgebase()
    client = toolset.client
    await client.create_collection(
        collection_name=WebPage.name,
        vectors_config=models.VectorParams(size=2, distance=models.Distance.COSINE),
    )
    await client.create_payload_index(
        collection_name=WebPage.name,
        field_name="id",
        field_schema=models.PayloadSchemaType.KEYWORD,
    )
    await client.create_payload_index(
        collection_name=WebPage.name,
        field_name="chunk_idx",
        field_schema=models.PayloadSchemaType.INTEGER,
    )
    return toolset


@pytest.mark.asyncio
async def test_query_returns_document_hits(kb, monkeypatch):
    toolset, ctx = kb
    hit = WebPage(
        id="doc-1",
        research_id="research-1",
        title="Example",
        url="https://example.com",
        text="text",
    )
    async def query(**kwargs):
        yield SimpleNamespace(hits=[hit])

    monkeypatch.setattr(WebPage, "query", classmethod(lambda cls, **kwargs: query(**kwargs)))

    result = await Query(
        ctx=ctx,
        toolset=toolset,
        query="question",
        research_id="research-1",
    ).run()

    assert result == [hit]


@pytest.mark.asyncio
async def test_query_reports_missing_collection_as_tool_failure(kb, monkeypatch):
    toolset, ctx = kb

    def query(**kwargs):
        raise ValueError("Collection WebPage not found")

    monkeypatch.setattr(WebPage, "query", classmethod(lambda cls, **kwargs: query(**kwargs)))

    with pytest.raises(ToolFailed, match="WebPage collection does not exist"):
        await Query(
            ctx=ctx,
            toolset=toolset,
            query="question",
            research_id="research-1",
        ).run()


@pytest.mark.asyncio
async def test_get_returns_selected_chunks(kb):
    toolset, ctx = kb
    calls = []

    async def scroll(**kwargs):
        calls.append(kwargs)
        return [
            SimpleNamespace(
                payload={
                    "id": "doc-1",
                    "research_id": "research-1",
                    "title": "Example",
                    "url": "https://example.com",
                    "text": "text",
                    "chunk_idx": 0,
                }
            )
        ], None

    toolset.client = SimpleNamespace(scroll=scroll)

    result = await Get(ctx=ctx, toolset=toolset, id="doc-1", chunks=[0]).run()

    assert result[0].id == "doc-1"
    assert calls[0]["collection_name"] == "WebPage"
    assert calls[0]["limit"] == 1


@pytest.mark.asyncio
async def test_client_supports_in_memory_location():
    client = Client(location=Client.MEMORY)

    assert client.location == Client.MEMORY
    assert (await client.get_collections()).collections == []


@pytest.mark.asyncio
async def test_webpage_builder_uses_runtime_documents():
    document = WebPage(
        id="page-1",
        research_id="research-1",
        title="Example",
        url="https://example.com",
        text="content",
    )
    builder = WebPageBuilder(
        document_type=WebPage,
        client=Client(location=Client.MEMORY),
        data=[document],
    )

    point = await anext(builder.points())

    assert point.document == document


def test_query_prefetch_adds_runtime_filter():
    chunk_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="chunk_idx",
                match=models.MatchAny(any=[0, 2]),
            )
        ]
    )
    query = SearchQuery("subject", limit=5, runtime_filter=chunk_filter)
    query.embedding = SimpleNamespace(
        sparse=models.SparseVector(indices=[1], values=[1.0]),
        dense=[0.1, 0.2],
        multi=[[0.1, 0.2]],
        simple=models.SparseVector(indices=[1], values=[1.0]),
    )

    assert len(query.filter["filter"].must) == 2
    assert query.filter["filter"].must[1] == chunk_filter
    assert all(
        prefetch.filter.must[1] == chunk_filter
        for prefetch in query.data["prefetch"].prefetch
    )


@pytest.mark.asyncio
async def test_kb_get_returns_selected_chunks(knowledgebase):
    document_type = WebPage
    doc_id = "research-page"
    points = []
    for chunk_idx in range(3):
        document = document_type(
            id=doc_id,
            research_id="research-1",
            title="Example",
            url="https://example.com",
            text=f"chunk {chunk_idx}",
            chunk_idx=chunk_idx,
            is_doc=False,
        )
        points.append(
            models.PointStruct(
                id=get_hash_int(f"{doc_id}/{chunk_idx}"),
                vector=[0.1, 0.2],
                payload=document.model_dump(),
            )
        )

    await knowledgebase.client.upload_points(
        collection_name=document_type.name,
        points=points,
    )
    ctx = RunContext(
        deps=SimpleNamespace(),
        model=None,
        usage=RunUsage(),
    )

    result = await Get(
        ctx=ctx,
        toolset=knowledgebase,
        id=doc_id,
        chunks=[2, 0],
    ).run()

    assert {document.chunk_idx for document in result} == {0, 2}
