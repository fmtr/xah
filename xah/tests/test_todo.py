import asyncio
from types import SimpleNamespace
from pydantic_ai import RunContext
from pydantic_ai.usage import RunUsage
from corio.iterator import ilist
from xah.toolsets.base.tool import Messages, Validation
from xah.toolsets.todo.item import TodoItem
from xah.toolsets.todo.toolset import Todo
from xah.toolsets.todo.write import Write


def context():
    toolset = Todo()
    deps = SimpleNamespace(toolsets=ilist([toolset]), approval_bridge=None)
    return RunContext(deps=deps, model=None, usage=RunUsage())


def test_write_uses_model_todos_and_updates_toolset():
    ctx = context()
    tool = Write(ctx=ctx, toolset=ctx.deps.toolsets.cls[Todo], todos=[TodoItem(content="one")])
    tool.validation = Validation()
    asyncio.run(tool.validate())
    assert tool.validation.messages == Messages()
    assert asyncio.run(tool.run()).startswith("Updated 1 todo")
