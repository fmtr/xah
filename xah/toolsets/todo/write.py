from pydantic import Field

from corio import strings
from corio.iterator import ilist
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.todo.item import TodoItem
from xah.toolsets.todo.output import TodoOutput


class Input(InputBase):
    todos: list[TodoItem] = Field(description="Complete replacement todo list.")

    @property
    def title(self):
        item_count = strings.suffix_plural(len(self.todos), "todo")
        return f"Replacing todo list with {item_count}"

    @property
    def content(self):
        item_count = strings.suffix_plural(len(self.todos), "item")
        return [self.content_block(f"Replace todo list with {item_count}")]

class Write(Tool, Input):
    """Replace the full todo list, including initial status metadata."""

    KIND = Kinds.MOVE

    async def run(self) -> TodoOutput:
        self.toolset.items = ilist(self.todos)
        self.toolset.feedback_state(self)

        todos = strings.suffix_plural(len(self.todos), "todo")
        return TodoOutput(
            items=list(self.toolset.items),
            message=f"Updated {todos}:",
            summary=self.toolset.summary,
        )
