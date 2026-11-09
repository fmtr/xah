from corio.function import ccp
from xah.class_collections import classes
from pydantic import Field
from pydantic_ai import ModelRetry

from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.todo.constants import TodoStatus
from xah.toolsets.todo.item import TodoItem


class Input(InputBase):
    todo_id: str = Field(description="ID of the todo to update.")
    status: TodoStatus = Field(description="New todo status.")

    @property
    def title(self):
        return f"Updating todo `{self.todo_id}` to `{self.status}`"

    @property
    def content(self):
        return [self.content_block(f"Todo {self.todo_id}: {self.status}")]

class UpdateStatus(Tool, Input):
    """Update one todo's status."""

    KIND = Kinds.THINK

    @classes
    def Validators(cls):
        return [ExistingTodo]

    @ccp
    def Output(cls) -> type[TodoItem]:
        return TodoItem

    async def run(self) -> TodoItem:
        todo = self.toolset.list.items.id[self.todo_id]
        todo.todo_status = self.status
        self.toolset.list.feedback_state(self)
        return todo


class ExistingTodo(UpdateStatus):
    async def validate(self):
        if self.todo_id not in self.toolset.list.items.id:
            raise ModelRetry(f"Todo with ID '{self.todo_id}' not found")
