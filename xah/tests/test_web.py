from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import RunContext, ToolFailed
from pydantic_ai.usage import RunUsage
from tavily import AsyncTavilyClient

from xah.toolsets.web.base import FetchResult
from xah.toolsets.web.fetch import Fetch
from xah.toolsets.web.research import HarnessResearch, Research
from xah.toolsets.web.request import Method, Request, Response
from xah.toolsets.web.search import Search
from xah.toolsets.web.toolset import Web


@pytest.fixture
def web():
    toolset = Web()
    toolset.client = AsyncMock()
    ctx = RunContext(deps=SimpleNamespace(), model=None, usage=RunUsage())
    return toolset, ctx


def test_web_provides_tavily_client():
    assert isinstance(Web().client, AsyncTavilyClient)


def test_web_exposes_fetch_research_and_request():
    assert Web.Tools == [Fetch, Research, Request]


def test_request_methods_preserve_uppercase_values():
    assert [method.value for method in Method] == [
        "DELETE",
        "GET",
        "HEAD",
        "OPTIONS",
        "PATCH",
        "POST",
        "PUT",
    ]


@pytest.mark.asyncio
async def test_request_uses_http_defaults(web):
    toolset, ctx = web
    response = MagicMock(status_code=200, text='{"ok": true}')
    response.headers = {"content-type": "application/json"}
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.request.return_value = response

    with patch("corio.https.AsyncClient", return_value=client):
        result = await Request(
            ctx=ctx,
            toolset=toolset,
            url="https://example.test/api",
        ).run()

    assert result == Response(
        status_code=200,
        headers={"content-type": "application/json"},
        body='{"ok": true}',
    )
    client.request.assert_awaited_once_with(
        method=Method.GET,
        url="https://example.test/api",
        headers={},
        content=None,
        params={},
        timeout=10.0,
        follow_redirects=True,
    )


@pytest.mark.asyncio
async def test_request_reports_failures(web):
    toolset, ctx = web
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.request.side_effect = OSError("connection failed")

    with patch("corio.https.AsyncClient", return_value=client):
        with pytest.raises(ToolFailed, match="connection failed"):
            await Request(ctx=ctx, toolset=toolset, url="https://example.test").run()


@pytest.mark.asyncio
async def test_fetch_returns_all_url_failures(web, monkeypatch):
    toolset, ctx = web

    async def fetch(self, urls):
        for url in urls:
            yield FetchResult(url=url, error="The request timed out.")

    monkeypatch.setattr(Fetch, "fetch", fetch)

    results = await Fetch(
        ctx=ctx,
        toolset=toolset,
        urls=["https://example.test"],
    ).run()

    assert results == [
        FetchResult(url="https://example.test", error="The request timed out.")
    ]


@pytest.mark.asyncio
async def test_fetch_returns_successes_and_failures_together(web, monkeypatch):
    toolset, ctx = web

    async def fetch(self, urls):
        yield FetchResult(url=urls[0], title="Example", text="Readable text")
        yield FetchResult(url=urls[1], error="The page was blocked.")

    monkeypatch.setattr(Fetch, "fetch", fetch)

    results = await Fetch(
        ctx=ctx,
        toolset=toolset,
        urls=["https://example.test", "https://blocked.test"],
    ).run()

    assert results == [
        FetchResult(
            url="https://example.test",
            title="Example",
            text="Readable text",
        ),
        FetchResult(url="https://blocked.test", error="The page was blocked."),
    ]


def test_research_harness_exposes_only_web_toolset():
    web = HarnessResearch.Toolsets[0]

    assert HarnessResearch.Toolsets == [web]


@pytest.mark.asyncio
async def test_search_uses_agent_friendly_defaults(web):
    toolset, ctx = web
    toolset.client.search.return_value = {"results": []}

    await Search(ctx=ctx, toolset=toolset, query="events").run()

    toolset.client.search.assert_awaited_once_with(
        query="events",
        search_depth="advanced",
        topic="general",
        max_results=5,
        include_answer="advanced",
        include_raw_content=False,
        include_images=False,
    )


@pytest.mark.asyncio
async def test_web_tools_report_search_failures(web):
    toolset, ctx = web
    toolset.client.search.side_effect = OSError("Name or service not known")

    with pytest.raises(ToolFailed, match="Name or service not known"):
        await Search(ctx=ctx, toolset=toolset, query="events").run()
