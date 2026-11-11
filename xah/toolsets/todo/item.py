from uuid import uuid4

from pydantic import Field
from pydantic_ai_todo.types import TodoItem as UpstreamTodoItem

from corio import hash
from xah.toolsets.base.output import Output
from xah.toolsets.base.projection.base import ProjectionContent
from xah.toolsets.todo.constants import TodoStatus


class TodoItem(Output):
    id: str = Field(
        default_factory=lambda: hash.get_hash_readable(str(uuid4()), length=4),
        description=UpstreamTodoItem.model_fields["id"].description,
    )
    todo_content: str = Field(
        alias="content",
        description=UpstreamTodoItem.model_fields["content"].description,
    )
    todo_status: TodoStatus = Field(
        default=TodoStatus.PENDING,
        alias="status",
        description=UpstreamTodoItem.model_fields["status"].description,
    )

    @property
    def delegated_content(self) -> str:
        return self.todo_content

    @property
    def text(self) -> str:
        return f"{self.todo_status.icon} [{self.id}] {self.delegated_content}"

    @property
    def updated_status_text(self) -> str:
        return f"Updated todo '{self.delegated_content}' status to '{self.todo_status}'"

    @property
    def agent(self) -> str:
        return self.updated_status_text

    @property
    def title(self) -> str:
        content_preview = self.preview(self.delegated_content, limit=20)
        return f"Updated todo `{content_preview}` to `{self.todo_status}`"

    @property
    def content(self) -> list[ProjectionContent]:
        return [self.content_block(self.text)]
