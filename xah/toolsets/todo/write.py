from pydantic import Field

from corio import strings
from corio.iterator import ilist
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.tool import Input as InputBase, Kinds, Tool
from xah.toolsets.todo.item import TodoItem


class Input(InputBase):
    todos: list[TodoItem] = Field(description="Complete replacement todo list.")

    def get_projection(self, request):
        count = len(self.todos)
        items = strings.suffix_plural(count, "items")
        return AcpToolProjection(
            content=[self.content_block(f"Replace todo list with {items}")],
            title="Update todo list",
        )

class Write(Tool, Input):
    """Replace the full todo list, including initial status metadata."""

    KIND = Kinds.EDIT

    async def run(self) -> str:
        self.toolset.items = ilist(self.todos)
        self.toolset.feedback_state(self)

        todos=strings.suffix_plural(len(self.todos), 'todo')
        msg=strings.trim(f"""
            Updated {todos}:

            {self.toolset.summary}
        """)
        return msg
