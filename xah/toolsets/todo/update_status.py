from cached_classproperty import cached_classproperty
from xah.class_collections import classes
from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from pydantic_ai import ModelRetry

from corio.function import ccp
from xah.toolsets.todo.projection import TodoProjection
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase, Tool
from xah.toolsets.todo.constants import TodoStatus


class Projection(TodoProjection):
    def start(self):
        return AcpToolProjection(
            content=[self.content(f"Todo {self.sig.todo_id}: {self.sig.status}")],
            title=f"Update todo {self.sig.todo_id}",
        )


class Signature(SignatureBase):
    todo_id: str = Field(description="ID of the todo to update.")
    status: TodoStatus = Field(description="New todo status.")


class UpdateStatus(Tool, Signature):
    """Update one todo's status."""

    KIND = Kinds.EDIT

    @ccp
    def Projection(cls):
        return Projection

    @classes
    def Validators(cls):
        return [ExistingTodo]

    async def run(self) -> str:
        todo = self.toolset.items.id[self.todo_id]
        todo.status = self.status
        self.toolset.feedback_state(self)
        return todo.updated_status_text


class ExistingTodo(UpdateStatus):
    async def validate(self):
        if self.todo_id not in self.toolset.items.id:
            raise ModelRetry(f"Todo with ID '{self.todo_id}' not found")
