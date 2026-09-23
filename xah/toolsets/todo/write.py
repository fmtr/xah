from pydantic import Field
from corio import strings
from corio.iterator import ilist
from xah.toolsets.base.tool import Tool
from xah.toolsets.todo.item import TodoItem
from xah.toolsets.todo.sig import TodoSig


class WriteSig(TodoSig):
    todos: list[TodoItem] = Field(description="Complete replacement todo list.")


class Write(Tool, WriteSig):
    """Replace the full todo list, including initial status metadata."""

    async def run(self) -> str:
        self.toolset.items = ilist(self.todos)
        return f"Updated {strings.suffix_plural(len(self.todos), 'todo')}:\n\n{self.toolset.summary}"
