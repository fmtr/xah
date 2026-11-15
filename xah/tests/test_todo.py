from types import SimpleNamespace

import pytest
from corio.iterator import ilist
from pydantic_ai import RunContext
from pydantic_ai.usage import RunUsage
from xah.toolsets.base.tool import Messages, Validation
from xah.toolsets.todo.constants import TodoStatus
from xah.toolsets.todo.item import TodoItem
from xah.toolsets.todo.read import Read
from xah.toolsets.todo.toolset import Todo
from xah.toolsets.todo.update_status import UpdateStatus
from xah.toolsets.todo.write import Write


def context():
    toolset = Todo()
    deps = SimpleNamespace(toolsets=ilist([toolset]), approval_bridge=None)
    return RunContext(deps=deps, model=None, usage=RunUsage())


@pytest.mark.asyncio
async def test_instructions_reflect_current_todo_items():
    ctx = context()
    toolset = ctx.deps.toolsets.cls[Todo]
    toolset.list.items.append(TodoItem(content="one"))

    instructions = toolset.list.instructions

    assert len(instructions) == 1
    assert "one" in instructions[0].content
    assert instructions[0].dynamic
    assert await toolset.get_instructions(ctx) == instructions


@pytest.mark.asyncio
async def test_read_returns_structured_items_and_flattens_for_agent():
    ctx = context()
    toolset = ctx.deps.toolsets.cls[Todo]
    toolset.list.items.append(TodoItem(id="abc123", content="one"))
    output = await Read(ctx=ctx, toolset=toolset).run()

    assert output is toolset.list
    assert "abc123" in output.agent
    assert "one" in output.agent
    assert len(output.content) == 2
    assert "abc123" in output.content[0].content.text
    assert "one" in output.content[0].content.text


@pytest.mark.asyncio
async def test_write_replaces_existing_todos_with_structured_output():
    ctx = context()
    todo_list = ctx.deps.toolsets.cls[Todo].list
    todo_list.items.append(TodoItem(id="stale", content="old item"))
    tool = Write(
        ctx=ctx,
        toolset=ctx.deps.toolsets.cls[Todo],
        todos=[TodoItem(id="new-item", content="one")],
    )
    tool.validation = Validation()
    await tool.validate()
    assert tool.validation.messages == Messages()

    output = await tool.run()

    assert output is todo_list
    assert [item.id for item in output.items] == ["new-item"]
    assert output.items[0].todo_content == "one"
    assert len(output.content) == 2
    assert "one" in output.content[0].content.text


@pytest.mark.asyncio
async def test_update_status_changes_the_existing_item():
    ctx = context()
    toolset = ctx.deps.toolsets.cls[Todo]
    toolset.list.items.append(TodoItem(id="abc123", content="one"))
    tool = UpdateStatus(
        ctx=ctx,
        toolset=toolset,
        todo_id="abc123",
        status=TodoStatus.COMPLETED,
    )

    output = await tool.run()

    assert output is toolset.list.items.id["abc123"]
    assert output.todo_status == TodoStatus.COMPLETED
    assert output.todo_content == "one"
    assert output.id == "abc123"
