import asyncio
from types import SimpleNamespace

import pytest
import pytest_asyncio
from pydantic_ai import RunContext, ToolFailed
from pydantic_ai.usage import RunUsage
from qdrant_client.http import models

from corio.db.search.client import Client
from xah.class_collections import classes
from corio.db.search.query import Query as SearchQuery
from corio.hash import get_hash_int

from xah.toolsets.kb.db import WebPage, WebPageBuilder
from xah.toolsets.kb.get import DocumentChunksOutput, Get
from xah.toolsets.kb.history import ResearchHistory
from xah.toolsets.kb.list import List
from xah.toolsets.kb.query import DocumentHitsOutput, Query
from xah.toolsets.kb.toolset import Knowledgebase


def test_knowledgebase_defaults_unknown_ids_to_web_pages():
    knowledgebase = Knowledgebase()

    assert knowledgebase.collection_for("research-1") is WebPage


@pytest.mark.parametrize(
    ("tool_type", "arguments"),
    [
        (Get, {"document_id": "doc-1", "chunks": [0]}),
        (Query, {"query": "synthetic query"}),
    ],
)
def test_read_tools_require_approval_for_protected_collections(tool_type, arguments):
    class ProtectedPage(WebPage):
        APPROVAL = True

    class ProtectedKnowledgebase(Knowledgebase):
        @classes
        def Collections(cls):
            return [ProtectedPage]

    toolset = ProtectedKnowledgebase()
    ctx = RunContext(
        deps=SimpleNamespace(toolsets=[toolset]),
        model=None,
        usage=RunUsage(),
    )
    tool = tool_type(
        ctx=ctx,
        toolset=toolset,
        collection_id=ProtectedPage.name,
        **arguments,
    )

    asyncio.run(tool.validate())

    assert tool.validation.approval
    assert len(tool.validation.messages.approval) == 1
    assert ProtectedPage.name in tool.validation.messages.approval[0]
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

    collection = result.collections[0]

    assert type(collection) is ResearchHistory
    assert collection.id == "research-1"
    assert collection.desc == "A completed investigation."
    assert result.agent == [
        {"id": "research-1", "desc": "A completed investigation."}
    ]


def test_kb_tools_use_standard_identifier_names():
    assert "collection_id" in Query.model_fields
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
    await client.create_payload_index(
        collection_name=WebPage.name,
        field_name="collection_id",
        field_schema=models.PayloadSchemaType.KEYWORD,
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
    calls = []

    async def query(**kwargs):
        calls.append(kwargs)
        yield SimpleNamespace(hits=[hit])

    monkeypatch.setattr(WebPage, "query", classmethod(lambda cls, **kwargs: query(**kwargs)))

    result = await Query(
        ctx=ctx,
        toolset=toolset,
        query="question",
        collection_id="research-1",
    ).run()

    assert result.hits == [hit]
    assert len(calls) == 1
    assert calls[0]["texts"] == ["question"]
    filter_condition = calls[0]["runtime_filter"].must[0]
    assert filter_condition.key == "collection_id"
    assert filter_condition.match.value == "research-1"


@pytest.mark.asyncio
async def test_query_projects_empty_results_as_a_text_block(kb, monkeypatch):
    toolset, ctx = kb

    async def query(**kwargs):
        yield SimpleNamespace(hits=[])

    monkeypatch.setattr(WebPage, "query", classmethod(lambda cls, **kwargs: query(**kwargs)))

    result = await Query(
        ctx=ctx,
        toolset=toolset,
        query="question",
        collection_id="research-1",
    ).run()
    result.request = SimpleNamespace(
        input=SimpleNamespace(title="Searching the knowledgebase", locations=None),
        status="completed",
        cwd=None,
    )

    assert result.hits == []
    assert len(result.projection.content) == 1
    assert result.projection.content[0].content.text


def test_get_projects_empty_chunks_as_a_text_block():
    output = DocumentChunksOutput(chunks=[])
    output.request = SimpleNamespace(
        input=SimpleNamespace(title="Getting chunks 0 from doc-1", locations=None),
        status="completed",
        cwd=None,
    )

    assert output.chunks == []
    assert len(output.projection.content) == 1
    assert output.projection.content[0].content.text


@pytest.mark.asyncio
async def test_query_propagates_collection_query_errors(kb, monkeypatch):
    toolset, ctx = kb
    error = ValueError("QUERY-FAILURE-2B")
    calls = []

    def query(**kwargs):
        calls.append(kwargs)
        raise error

    monkeypatch.setattr(WebPage, "query", classmethod(lambda cls, **kwargs: query(**kwargs)))

    with pytest.raises(ValueError) as exc_info:
        await Query(
            ctx=ctx,
            toolset=toolset,
            query="question",
            collection_id="research-1",
        ).run()

    assert exc_info.value is error
    assert len(calls) == 1
    assert calls[0]["texts"] == ["question"]
    assert calls[0]["client"] is toolset.client
    filter_condition = calls[0]["runtime_filter"].must[0]
    assert filter_condition.key == "collection_id"
    assert filter_condition.match.value == "research-1"


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

    assert result.chunks[0].id == "doc-1"
    assert len(calls) == 1
    assert calls[0]["collection_name"] == "WebPage"
    assert calls[0]["limit"] == 1
    filter_conditions = calls[0]["scroll_filter"].must
    assert filter_conditions[0].key == "id"
    assert filter_conditions[0].match.value == "doc-1"
    assert filter_conditions[1].key == "chunk_idx"
    assert filter_conditions[1].match.any == [0]


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

    assert {(document.chunk_idx, document.text) for document in result.chunks} == {
        (0, "chunk 0"),
        (2, "chunk 2"),
    }


@pytest.mark.asyncio
async def test_kb_get_does_not_return_chunks_from_another_collection(knowledgebase):
    document_id = "shared-document-id"
    document = WebPage(
        id=document_id,
        collection_id="research-2",
        title="Other research",
        url="https://example.com/other",
        text="unrelated document",
        chunk_idx=0,
        is_doc=False,
    )
    knowledgebase.client.upload_points(
        collection_name=WebPage.name,
        points=[
            models.PointStruct(
                id=get_hash_int(f"{document_id}/0"),
                vector=[0.1, 0.2],
                payload=document.model_dump(),
            ),
        ],
    )
    ctx = RunContext(deps=SimpleNamespace(), model=None, usage=RunUsage())

    result = await Get(
        ctx=ctx,
        toolset=knowledgebase,
        collection_id="research-1",
        document_id=document_id,
        chunks=[0],
    ).run()

    assert result.chunks == []
