from typing import ClassVar
from uuid import uuid4

from pydantic import Field
from pydantic_ai_todo.types import TodoItem as UpstreamTodoItem

from corio import dm
from xah.toolsets.todo.constants import BLOCKED, COMPLETED, IN_PROGRESS, PENDING, TodoStatus


class TodoItem(dm.Base):
    STATUS_ICONS: ClassVar = {PENDING: "[ ]", IN_PROGRESS: "[*]", COMPLETED: "[x]", BLOCKED: "[!]"}

    id: str = Field(
        default_factory=lambda: uuid4().hex[:8],
        description=UpstreamTodoItem.model_fields["id"].description,
    )
    content: str = Field(description=UpstreamTodoItem.model_fields["content"].description)
    status: TodoStatus = Field(default=PENDING, description=UpstreamTodoItem.model_fields["status"].description)

    @property
    def text(self) -> str:
        return f"{self.STATUS_ICONS[self.status]} [{self.id}] {self.content}"

    @property
    def updated_status_text(self) -> str:
        return f"Updated todo '{self.content}' status to '{self.status}'"
