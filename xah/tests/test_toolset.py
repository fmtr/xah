import pytest
from pydantic_ai import ModelRetry, ToolFailed

from xah.toolsets.base.toolset import Toolset


@pytest.mark.asyncio
async def test_raise_errors_returns_method_result():
    toolset = Toolset()

    async def method(value):
        return value

    assert await toolset.raise_errors(method, "result") == "result"


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ModelRetry("retry"), ToolFailed("failed")])
async def test_raise_errors_preserves_framework_errors(error):
    toolset = Toolset()

    async def method():
        raise error

    with pytest.raises(type(error)) as raised:
        await toolset.raise_errors(method)

    assert raised.value is error


@pytest.mark.asyncio
async def test_raise_errors_logs_and_wraps_unexpected_errors(monkeypatch):
    toolset = Toolset()
    logged = []
    monkeypatch.setattr("xah.toolsets.base.toolset.logger.error", logged.append)

    async def method():
        raise ValueError("unexpected")

    with pytest.raises(ToolFailed, match="unexpected") as raised:
        await toolset.raise_errors(method)

    assert logged == ["unexpected"]
    assert isinstance(raised.value.__cause__, ValueError)
