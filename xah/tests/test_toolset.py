from types import SimpleNamespace

import pytest
from corio import Path
from corio.iterator import ilist
from pydantic_ai import ModelRetry, RunContext, ToolFailed
from pydantic_ai.exceptions import UserError
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from xah.toolsets.base.tool import ToolState
from xah.toolsets.base.toolset import Toolset
from xah.toolsets.fs.toolset import Files
from xah.toolsets.management.list import List
from xah.toolsets.management.toolset import Management


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
async def test_management_list_result_stays_typed(tmp_path):
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
    name = management.get_name(List)

    result = await management.call_tool(name, {}, ctx, tools[name])

    assert result.toolsets == [management.info, files.info]
    progress = type(management).project_progress(
        name,
        raw_input={},
        raw_output=result,
        serialized_output="[]",
        status="completed",
    )

    assert progress.title == name
    assert progress.status == "completed"


@pytest.mark.asyncio
async def test_management_list_feedbacks_after_first_call_and_resets_after_compress(
    monkeypatch, tmp_path
):
    settings = SimpleNamespace(path=SimpleNamespace(home=Path(".agent")))
    management = Management(settings=settings, cwd=Path(tmp_path))
    files = Files(settings=settings, cwd=Path(tmp_path))
    deps = SimpleNamespace(toolsets=SimpleNamespace(permitted=ilist([management, files])))
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=RunUsage(),
        tool_call_id="call-1",
    )
    feedback = []
    monkeypatch.setattr(List, "feedback", lambda self, message: feedback.append(message))
    tool = List(
        ctx=ctx,
        toolset=management,
        state=management.state_for(List, List),
    )

    first_result = await tool.run()

    assert isinstance(tool.state, ToolState)
    assert tool.state.called
    assert first_result.toolsets == [management.info, files.info]
    assert await tool.run() == first_result
    assert feedback == [
        "You have already listed the toolsets. These will not change during a given session."
    ]

    tool.state.after_compress()

    assert not tool.state.called
    assert await tool.run() == first_result


def test_feedback_logs_messages_without_active_run(monkeypatch):
    logged = []

    def enqueue(_message):
        raise UserError("run ended")

    monkeypatch.setattr(
        "xah.toolsets.base.toolset.logger.warning",
        lambda message: logged.append(message),
    )

    ctx = SimpleNamespace(enqueue=enqueue, pending_messages=None)
    assert Toolset.feedback(ctx, "late feedback") is None
    assert len(logged) == 1
    assert logged[0].startswith(
        "Toolset feedback could not be enqueued: [HARNESS FEEDBACK]"
    )
    assert "late feedback" in logged[0]


def test_feedback_logs_unrelated_user_errors_without_failing_the_run(monkeypatch):
    logged_errors = []
    logged_warnings = []
    error = UserError("invalid feedback")

    def enqueue(_message):
        raise error

    monkeypatch.setattr(
        "xah.toolsets.base.toolset.logger.error",
        lambda message, **kwargs: logged_errors.append((message, kwargs)),
    )
    monkeypatch.setattr(
        "xah.toolsets.base.toolset.logger.warning",
        lambda message: logged_warnings.append(message),
    )

    ctx = SimpleNamespace(enqueue=enqueue, pending_messages=[])
    assert Toolset.feedback(ctx, "bad feedback") is None

    assert logged_errors == [
        ("Toolset feedback enqueue failed: invalid feedback", {"_exc_info": True})
    ]
    assert logged_warnings == [
        "Toolset feedback could not be enqueued: [HARNESS FEEDBACK]\n\nbad feedback"
    ]
