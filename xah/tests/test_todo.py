import asyncio
from types import SimpleNamespace
from pydantic_ai import RunContext
from pydantic_ai.usage import RunUsage
from corio.iterator import ilist
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


def test_instructions_are_a_property_without_context():
    ctx = context()
    toolset = ctx.deps.toolsets.cls[Todo]
    toolset.list.items.append(TodoItem(content="one"))

    instructions = toolset.list.instructions

    assert len(instructions) == 1
    assert "one" in instructions[0].content
    assert instructions[0].dynamic
    assert asyncio.run(toolset.get_instructions(ctx)) == instructions


def test_read_returns_structured_items_and_flattens_for_agent():
    ctx = context()
    toolset = ctx.deps.toolsets.cls[Todo]
    toolset.list.items.append(TodoItem(id="abc123", content="one"))
    assert len(TodoItem(content="one").id) == 4

    output = asyncio.run(Read(ctx=ctx, toolset=toolset).run())

    assert output is toolset.list
    assert "1. ⏳ [abc123] one" in output.agent
    assert len(output.content) == 2
    assert output.content[0].content.text == "⏳ [abc123] one"


def test_write_uses_model_todos_and_returns_structured_output():
    ctx = context()
    tool = Write(ctx=ctx, toolset=ctx.deps.toolsets.cls[Todo], todos=[TodoItem(content="one")])
    tool.validation = Validation()
    asyncio.run(tool.validate())
    assert tool.validation.messages == Messages()

    output = asyncio.run(tool.run())

    assert output is ctx.deps.toolsets.cls[Todo].list
    assert output.agent.startswith("Current todos:")
    assert len(output.content) == 2
    assert output.content[0].content.text.endswith("one")


def test_update_output_title_uses_todo_status_and_projects_item():
    ctx = context()
    toolset = ctx.deps.toolsets.cls[Todo]
    toolset.list.items.append(TodoItem(id="abc123", content="one"))
    tool = UpdateStatus(
        ctx=ctx,
        toolset=toolset,
        todo_id="abc123",
        status=TodoStatus.COMPLETED,
    )

    output = asyncio.run(tool.run())

    assert output is toolset.list.items.id["abc123"]
    assert output.title == "Updated todo `one` to `completed`"
    assert output.agent.startswith("Updated todo 'one' status to 'completed'")
    assert output.content[0].content.text == "✅ [abc123] one"


def test_update_output_title_previews_long_todo_content():
    todo = TodoItem(content="This todo title is considerably longer than twenty characters")

    preview = todo.preview(todo.todo_content, limit=20)

    assert preview == "This todo…haracters"
    assert todo.title == f"Updated todo `{preview}` to `pending`"
