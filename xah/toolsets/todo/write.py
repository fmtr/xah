from pydantic import Field

from corio import strings
from corio.iterator import ilist
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.todo.item import TodoItem


class Input(InputBase):
    todos: list[TodoItem] = Field(description="Complete replacement todo list.")

    @property
    def title(self):
        item_count = strings.suffix_plural(len(self.todos), "todo")
        return f"Replacing todo list with {item_count}"

    @property
    def projection(self):
        item_count = strings.suffix_plural(len(self.todos), "item")
        return AcpToolProjection(
            content=[self.content_block(f"Replace todo list with {item_count}")],
            title=self.title,
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
