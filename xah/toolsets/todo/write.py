from pydantic import Field

from corio import strings
from corio.function import ccp
from corio.iterator import ilist
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.todo.item import TodoItem
from xah.toolsets.todo.list import TodoList


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

    KIND = Kinds.THINK

    @ccp
    def Output(cls) -> type[TodoList]:
        return TodoList

    async def run(self) -> TodoList:
        self.toolset.list.items = ilist(self.todos)
        self.toolset.list.feedback_state(self)
        return self.toolset.list
