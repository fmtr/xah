from types import SimpleNamespace

import pytest
from corio import Path
from corio.iterator import ilist
from pydantic_ai import ModelRetry, RunContext, ToolFailed
from pydantic_ai.exceptions import UserError
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from xah.toolsets.fs.toolset import Files
from xah.toolsets.management.list import List
from xah.toolsets.management.toolset import Management
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
    monkeypatch.setattr(
        "xah.toolsets.base.toolset.logger.error",
        lambda message, **kwargs: logged.append((message, kwargs)),
    )

    async def method():
        raise ValueError("unexpected")

    with pytest.raises(ToolFailed, match="Internal error") as raised:
        await toolset.raise_errors(method)

    assert logged == [("unexpected", {"_exc_info": True})]
    assert raised.value.__cause__ is None


def test_description_does_not_inherit_function_toolset_docstring():
    class UndocumentedToolset(Toolset):
        pass

    assert UndocumentedToolset.description is None


@pytest.mark.asyncio
async def test_management_list_result_can_be_externalized(tmp_path):
    settings = SimpleNamespace(path=SimpleNamespace(home=Path(".agent")))
    management = Management(settings=settings, cwd=Path(tmp_path))
    files = Files(settings=settings, cwd=Path(tmp_path))
    deps = SimpleNamespace(
        toolsets=SimpleNamespace(permitted=ilist([management, files])),
        settings=settings,
        cwd_default=Path(tmp_path),
    )
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=RunUsage(),
        tool_call_id="call-1",
    )
    tools = await management.get_tools(ctx)
    name = management.tool_name(List)

    result = await management.call_tool(name, {}, ctx, tools[name])

    assert result == [management.info, files.info]
    assert not (Path(tmp_path) / ".agent" / "artifacts" / "call-1.json").exists()


def test_feedback_logs_messages_after_run_completion(monkeypatch):
    logged = []

    def enqueue(_message):
        raise UserError("run ended")

    monkeypatch.setattr(
        "xah.toolsets.base.toolset.logger.warning",
        lambda message: logged.append(message),
    )

    assert Toolset.feedback(SimpleNamespace(enqueue=enqueue), "late feedback") is None
    assert len(logged) == 1
    assert logged[0].startswith(
        "Toolset feedback occurred after the agent run completed: [HARNESS FEEDBACK]"
    )
    assert "late feedback" in logged[0]
