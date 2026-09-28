from types import SimpleNamespace

import pytest
from cached_classproperty import cached_classproperty
from pydantic_ai import RunContext
from pydantic_ai.usage import RunUsage

from corio.db.search.document import Document
from corio.hash import get_hash_int
from corio.iterator import ilist

from xah.toolsets.kb.get import Get
from xah.toolsets.kb.list import List
from xah.toolsets.kb.query import Query
from xah.toolsets.kb.toolset import Knowledgebase


class DummyDocument(Document):
    """Document model used by the knowledgebase tool tests."""


class DummyKnowledgebase(Knowledgebase):
    @cached_classproperty
    def DOCUMENTS(cls):
        return [DummyDocument]


@pytest.fixture
def kb():
    toolset = DummyKnowledgebase()
    toolset.client = object()
    ctx = RunContext(deps=SimpleNamespace(toolsets=ilist([toolset])), model=None, usage=RunUsage())
    return toolset, ctx


@pytest.mark.asyncio
async def test_list_returns_available_document_types(kb):
    toolset, ctx = kb

    result = await List(ctx=ctx, toolset=toolset).run()

    assert "DummyDocument:" in result


@pytest.mark.asyncio
async def test_query_returns_document_hits(kb, monkeypatch):
    toolset, ctx = kb
    hit = DummyDocument(id="doc-1", text="text")
    monkeypatch.setattr(DummyDocument, "query", classmethod(lambda cls, **kwargs: iter([SimpleNamespace(hits=[hit])])))

    result = await Query(ctx=ctx, toolset=toolset, doc_type="DummyDocument", query="question").run()

    assert "doc-1" in result
    assert "Full documents should be fetched using the `DummyKnowledgebase-Get` tool." in result


@pytest.mark.asyncio
async def test_get_returns_document(kb):
    toolset, ctx = kb
    calls = []

    def retrieve(**kwargs):
        calls.append(kwargs)
        return [SimpleNamespace(payload={"id": "doc-1", "text": "text"})]

    toolset.client = SimpleNamespace(retrieve=retrieve)

    result = await Get(ctx=ctx, toolset=toolset, doc_type="DummyDocument", id="doc-1").run()

    assert "doc-1" in result
    assert calls == [{
        "collection_name": "DummyDocument",
        "ids": [get_hash_int("doc-1")],
        "with_payload": True,
        "with_vectors": False,
    }]
