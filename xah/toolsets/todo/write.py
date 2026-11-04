from pydantic import Field

from corio import strings
from corio.iterator import ilist
from corio.function import ccp
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.todo.projection import TodoProjection
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase, Tool
from xah.toolsets.todo.item import TodoItem


class Projection(TodoProjection):
    def start(self):
        count = len(self.sig.todos)
        items=strings.suffix_plural(count, 'items')
        return AcpToolProjection(
            content=[self.content(f"Replace todo list with {items}")],
            title="Update todo list",
        )


class Signature(SignatureBase):
    todos: list[TodoItem] = Field(description="Complete replacement todo list.")


class Write(Tool, Signature):
    """Replace the full todo list, including initial status metadata."""

    KIND = Kinds.EDIT

    @ccp
    def Projection(cls):
        return Projection

    async def run(self) -> str:
        self.toolset.items = ilist(self.todos)
        self.toolset.feedback_state(self)

        todos=strings.suffix_plural(len(self.todos), 'todo')
        msg=strings.trim(f"""
            Updated {todos}:

            {self.toolset.summary}
        """)
        return msg
