from functools import cached_property

from cached_classproperty import cached_classproperty
from pydantic import Field
from pydantic_ai import ModelRetry

from xah.toolsets.base.tool import Tool
from xah.toolsets.todo.constants import TodoStatus


class UpdateStatus(Tool):
    """Update one todo's status."""

    todo_id: str = Field(description="ID of the todo to update.")
    status: TodoStatus = Field(description="New todo status.")

    @cached_classproperty
    def VALIDATORS(cls):
        return [ExistingTodo]

    async def run(self) -> str:
        todo = self.toolset.items.id[self.todo_id]
        todo.status = self.status
        return todo.updated_status_text


class ExistingTodo(UpdateStatus):
    @cached_property
    def enabled(self) -> bool:
        return True

    async def validate(self) -> list[str]:
        if self.todo_id not in self.toolset.items.id:
            raise ModelRetry(f"Todo with ID '{self.todo_id}' not found")
        return []
