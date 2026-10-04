from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic_ai import RunContext, ToolFailed
from pydantic_ai.usage import RunUsage
from tavily import AsyncTavilyClient

from xah.toolsets.web.research import Research
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


def test_web_exposes_search_and_research_only():
    assert Web.TOOLS == [Search, Research]


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
