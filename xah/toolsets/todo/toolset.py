from collections import Counter

from cached_classproperty import cached_classproperty

from corio import strings
from corio.iterator import ilist
from xah.constants import TODO_STATE_END, TODO_STATE_START
from xah.toolsets.base.toolset import Toolset
from xah.toolsets.todo.constants import COMPLETED, TODO_STATUSES
from xah.toolsets.todo.item import TodoItem

TODO_SYSTEM_PROMPT = strings.trim("""
    ## Task Management

    Use Todo-Read, Todo-Write, and Todo-UpdateStatus. Keep exactly one task in progress.
""")


class Todo(Toolset):
    """Todo list tools."""

    EMPTY_FEEDBACK = "No todos are currently defined. Use Todo-Write to create tasks."
    COMPLETED_FEEDBACK = "All tasks are completed; respond to the user."

    def feedback_state(self, tool):
        if not self.items:
            tool.feedback(self.EMPTY_FEEDBACK)
            return
        if self.all_completed:
            tool.feedback(self.COMPLETED_FEEDBACK)

    @cached_classproperty
    def TOOLS(cls):
        from xah.toolsets.todo.read import Read
        from xah.toolsets.todo.update_status import UpdateStatus
        from xah.toolsets.todo.write import Write

        return [Read, Write, UpdateStatus]

    def __init__(self, **kwargs):
        self.items = ilist[TodoItem]()
        super().__init__(**kwargs)

    @property
    def summary(self) -> str:
        counts = Counter(todo.status for todo in self.items)
        summary = strings.join((f"{counts[status]} {status}" for status in TODO_STATUSES), sep=", ")
        text = f"Summary: {summary}"

        return text

    @property
    def all_completed(self) -> bool:
        return bool(self.items) and all(todo.status == COMPLETED for todo in self.items)

    @property
    def text(self) -> str:
        if not self.items:
            return "No todos in the list."

        body = strings.join((f"{index}. {todo.text}" for index, todo in enumerate(self.items, 1)), sep="\n")
        return f"Current todos:\n\n{body}\n\n{self.summary}"

    @property
    def system_prompt(self) -> str:
        if not self.items:
            return TODO_SYSTEM_PROMPT

        body = strings.join((f"- {todo.text}" for todo in self.items), sep="\n")
        return f"{TODO_SYSTEM_PROMPT}\n\n{TODO_STATE_START}\n{body}\n{TODO_STATE_END}"
