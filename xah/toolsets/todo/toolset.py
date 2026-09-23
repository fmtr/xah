from collections import Counter
from corio import strings
from corio.iterator import ilist
from xah.constants import TODO_STATE_END, TODO_STATE_START
from xah.toolsets.base.toolset import Base
from xah.toolsets.todo.constants import COMPLETED, TODO_STATUSES
from xah.toolsets.todo.item import TodoItem
from xah.toolsets.todo.read import Read
from xah.toolsets.todo.update_status import UpdateStatus
from xah.toolsets.todo.write import Write

TODO_SYSTEM_PROMPT = strings.trim("""
    ## Task Management

    Use Todo-Read, Todo-Write, and Todo-UpdateStatus. Keep exactly one task in progress.
""")


class Todo(Base):
    """Todo list tools."""
    TOOLS = (Read, Write, UpdateStatus)

    def __init__(self, **kwargs):
        self.items = ilist[TodoItem]()
        super().__init__(**kwargs)

    @property
    def summary(self) -> str:
        counts = Counter(todo.status for todo in self.items)
        summary = strings.join((f"{counts[status]} {status}" for status in TODO_STATUSES), sep=", ")
        text = f"Summary: {summary}"

        if counts[COMPLETED] == len(self.items):
            return f"{text}. All tasks are completed; respond to the user."

        return text

    @property
    def text(self) -> str:
        if not self.items:
            return "No todos in the list. Use Todo-Write to create tasks."

        body = strings.join((f"{index}. {todo.text}" for index, todo in enumerate(self.items, 1)), sep="\n")
        return f"Current todos:\n\n{body}\n\n{self.summary}"

    @property
    def system_prompt(self) -> str:
        if not self.items:
            return TODO_SYSTEM_PROMPT

        body = strings.join((f"- {todo.text}" for todo in self.items), sep="\n")
        return f"{TODO_SYSTEM_PROMPT}\n\n{TODO_STATE_START}\n{body}\n{TODO_STATE_END}"
