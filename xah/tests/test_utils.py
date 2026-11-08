from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from corio.iterator import ilist
from pydantic_ai import RunContext
from pydantic_ai.usage import RunUsage

from xah.toolsets.base.output import OutputString
from xah.toolsets.utils.sleep import Sleep
from xah.toolsets.utils.toolset import Utils


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (3, "Slept for 3 seconds."),
        (90, "Slept for 1 minute and 30 seconds."),
    ],
)
@pytest.mark.asyncio
async def test_sleep_waits_for_requested_duration(monkeypatch, seconds, expected):
    sleep = AsyncMock()
    monkeypatch.setattr("xah.toolsets.utils.sleep.asyncio.sleep", sleep)

    toolset = Utils()
    ctx = RunContext(deps=SimpleNamespace(toolsets=ilist([toolset]), approval_bridge=None), model=None, usage=RunUsage())
    result = await Sleep(ctx=ctx, toolset=toolset, seconds=seconds).run()

    assert result == expected

    output = OutputString(output=result)
    output.request = SimpleNamespace(
        input=Sleep.input.model_validate({"seconds": seconds}),
        status="completed",
    )
    assert output.projection.content[0].content.text == expected
    sleep.assert_awaited_once_with(float(seconds))


def test_sleep_input_projection_uses_humanized_duration():
    input_model = Sleep.input.model_validate({"seconds": 90})

    assert input_model.projection.title == "Sleeping for 1 minute and 30 seconds"


def test_sleep_limits_wait_duration():
    with pytest.raises(ValueError):
        Sleep(seconds=121)
