from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from corio.iterator import ilist
from pydantic_ai import RunContext
from pydantic_ai.usage import RunUsage

from xah.toolsets.utils.sleep import Sleep
from xah.toolsets.utils.toolset import Utils


@pytest.mark.asyncio
async def test_sleep_waits_for_requested_duration(monkeypatch):
    sleep = AsyncMock()
    monkeypatch.setattr("xah.toolsets.utils.sleep.asyncio.sleep", sleep)

    toolset = Utils()
    ctx = RunContext(deps=SimpleNamespace(toolsets=ilist([toolset])), model=None, usage=RunUsage())
    result = await Sleep(ctx=ctx, toolset=toolset, seconds=3).run()

    assert result == "Slept for 3 seconds."
    sleep.assert_awaited_once_with(3.0)


def test_sleep_limits_wait_duration():
    with pytest.raises(ValueError):
        Sleep(seconds=121)
