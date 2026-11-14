from types import SimpleNamespace

import pytest
from corio import Path
from corio.iterator import ilist
from pydantic_ai import ModelRetry, RunContext, ToolFailed
from pydantic_ai.exceptions import UserError
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from xah.toolsets.base.toolset import Toolset
from xah.toolsets.fs.toolset import Files
from xah.toolsets.management.activate import Activate
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


@pytest.mark.asyncio
async def test_management_instructions_list_toolsets_individually(tmp_path):
    settings = SimpleNamespace(path=SimpleNamespace(home=Path(".agent")))
    management = Management(settings=settings, cwd=Path(tmp_path))
    files = Files(settings=settings, cwd=Path(tmp_path), activated=True)

    class InactiveFiles(Files):
        pass

    inactive = InactiveFiles(settings=settings, cwd=Path(tmp_path), activated=False)
    ctx = RunContext(
        deps=SimpleNamespace(
            toolsets=SimpleNamespace(permitted=ilist([management, files, inactive]))
        ),
        model=TestModel(),
        usage=RunUsage(),
        tool_call_id="call-1",
    )

    instructions = await management.get_instructions(ctx)

    assert Management.get_tool("List", None) is None
    assert Management.get_tool("Activate") is Activate
    activate_name = management.get_name(Activate)
    assert len(instructions) == 2
    activated, available = instructions
    assert all(instruction.dynamic for instruction in instructions)
    assert "## Already Activated Toolsets" in activated.content
    assert "## Available Toolsets" in available.content
    assert "not yet activated, but are available" in available.content
    assert "## Available but Not Activated Toolsets" not in available.content
    assert f"`{activate_name}`" in available.content
    assert "already activated and available" in activated.content
    assert f"Never call `{activate_name}` for any listed ID again." in activated.content
    assert "remain active for the entire session" in activated.content
    assert "do not request activation on future turns" in activated.content
    assert "Use their tools directly." in activated.content
    assert "- `Files`" in activated.content
    assert "Toolset ID: **InactiveFiles**" in available.content
    assert "#### InactiveFiles" not in available.content
    assert "Filesystem reading, writing, editing, moving, and searching tools." in available.content
    assert "**Contains**" in available.content
    assert "- `Read`" in available.content
    assert "- `Write`" in available.content
    assert "Status:" not in available.content
    assert "Access:" not in available.content
    assert "InactiveFiles-Read" not in available.content


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
