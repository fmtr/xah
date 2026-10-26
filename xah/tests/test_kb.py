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
from xah.toolsets.kb.history import ResearchHistory
from xah.toolsets.kb.list import List
from xah.toolsets.kb.query import Query
from xah.toolsets.kb.toolset import Knowledgebase


def test_knowledgebase_defaults_unknown_ids_to_web_pages():
    knowledgebase = Knowledgebase()

    assert knowledgebase.collection_for("research-1") is WebPage


def test_read_tools_expose_collection_validator_classes():
    knowledgebase = Knowledgebase()

    assert Get.Validators[0].__name__ == "CollectionValidator"
    assert Query.Validators[0].__name__ == "CollectionValidator"
    knowledgebase.states


def test_research_history_tracks_prompts_with_ilist_lookup():
    history = ResearchHistory.Prompts(
        id="research-1",
        desc="A completed investigation.",
        prompts=["first prompt"],
    )

    assert history.id == "research-1"
    assert history.prompts == ["first prompt"]


@pytest.mark.asyncio
async def test_list_converts_prompt_history_to_research_history():
    knowledgebase = Knowledgebase()
    knowledgebase.history.append(
        ResearchHistory.Prompts(
            id="research-1",
            desc="A completed investigation.",
            prompts=["first prompt"],
        )
    )

    result = await List.model_construct(toolset=knowledgebase).run()

    assert type(result[0]) is ResearchHistory
    assert result[0].id == "research-1"


def test_kb_tools_use_standard_identifier_names():
    assert "collection_id" in Query.model_fields
    assert Query.model_fields["collection_id"].description == "Collection ID to search."
    assert "collection_id" in Get.model_fields
    assert "document_id" in Get.model_fields
    assert "id" not in Get.model_fields


@pytest.fixture
def kb():
    toolset = Knowledgebase()
    ctx = RunContext(
        deps=SimpleNamespace(toolsets=[toolset]),
        model=None,
        usage=RunUsage(),
        pending_messages=[],
    )
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
        collection_id="research-1",
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
        collection_id="research-1",
    ).run()

    assert result == [hit]


@pytest.mark.asyncio
async def test_query_reports_missing_collection_as_tool_failure(kb, monkeypatch):
    toolset, ctx = kb

    def query(**kwargs):
        raise ValueError("Collection WebPage not found")

    monkeypatch.setattr(WebPage, "query", classmethod(lambda cls, **kwargs: query(**kwargs)))

    with pytest.raises(ValueError, match="Collection WebPage not found"):
        await Query(
            ctx=ctx,
            toolset=toolset,
            query="question",
            collection_id="research-1",
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
                    "collection_id": "research-1",
                    "title": "Example",
                    "url": "https://example.com",
                    "text": "text",
                    "chunk_idx": 0,
                }
            )
        ], None

    toolset.client = SimpleNamespace(scroll=scroll)

    result = await Get(
        ctx=ctx,
        toolset=toolset,
        collection_id="research-1",
        document_id="doc-1",
        chunks=[0],
    ).run()

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
        collection_id="research-1",
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
            collection_id="research-1",
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

    knowledgebase.client.upload_points(
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
        collection_id="research-1",
        document_id=doc_id,
        chunks=[2, 0],
    ).run()

    assert {document.chunk_idx for document in result} == {0, 2}
