from functools import cached_property
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.messages import InstructionPart

from xah.class_collections import classes
from xah.toolsets.base.toolset import Toolset
from xah.toolsets.todo.list import TodoList


class Todo(Toolset):
    """Todo list tools."""

    @classes
    def Tools(cls):
        from xah.toolsets.todo.read import Read
        from xah.toolsets.todo.update_status import UpdateStatus
        from xah.toolsets.todo.write import Write

        return [Read, Write, UpdateStatus]

    @cached_property
    def list(self) -> TodoList:
        return TodoList()

    async def get_instructions(self, ctx: RunContext[Any]) -> list[InstructionPart]:
        return await self.list.get_instructions(ctx)
