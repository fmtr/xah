from corio.function import ccp
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool

from xah.toolsets.todo.list import TodoList


class Input(InputBase):
    @property
    def title(self):
        return "Reading todos"

    @property
    def content(self):
        return [self.content_block("Read current todo list")]


class Read(Tool, Input):
    """Read the current todo list and task IDs."""

    KIND = Kinds.THINK

    @ccp
    def Output(cls) -> type[TodoList]:
        return TodoList

    async def run(self) -> TodoList:
        self.toolset.list.feedback_state(self)
        return self.toolset.list
