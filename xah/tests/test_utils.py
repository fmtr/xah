from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from corio.iterator import ilist
from pydantic_ai import RunContext
from pydantic_ai.usage import RunUsage

from xah.toolsets.utils.sleep import Sleep
from xah.toolsets.utils.toolset import Utils


@pytest.mark.parametrize(
    "seconds",
    [3, 90],
)
@pytest.mark.asyncio
async def test_sleep_waits_for_requested_duration(monkeypatch, seconds):
    sleep = AsyncMock()
    monkeypatch.setattr("xah.toolsets.utils.sleep.asyncio.sleep", sleep)

    toolset = Utils()
    ctx = RunContext(deps=SimpleNamespace(toolsets=ilist([toolset]), approval_bridge=None), model=None, usage=RunUsage())
    result = await Sleep(ctx=ctx, toolset=toolset, seconds=seconds).run()

    assert isinstance(result, str)
    sleep.assert_awaited_once_with(float(seconds))


def test_sleep_rejects_negative_durations():
    with pytest.raises(ValueError):
        Sleep(seconds=-0.1)
