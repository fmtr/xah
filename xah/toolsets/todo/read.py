from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.todo.output import TodoOutput


class Input(InputBase):
    @property
    def title(self):
        return "Reading todos"

    @property
    def content(self):
        return [self.content_block("Read current todo list")]



class Read(Tool, Input):
    """Read the current todo list and task IDs."""

    KIND = Kinds.READ

    async def run(self) -> TodoOutput:
        self.toolset.feedback_state(self)
        items = list(self.toolset.items)
        message = "Current todos:" if items else "No todos in the list."
        summary = self.toolset.summary if items else ""
        return TodoOutput(items=items, message=message, summary=summary)
