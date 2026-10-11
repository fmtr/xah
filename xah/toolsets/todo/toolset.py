from collections import Counter
from typing import Any

from cached_classproperty import cached_classproperty
from xah.class_collections import classes

from corio import strings
from corio.iterator import ilist
from pydantic_ai import RunContext
from pydantic_ai.messages import InstructionPart
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

    @classes
    def Tools(cls):
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

    async def get_instructions(self, ctx: RunContext[Any]) -> list[InstructionPart]:
        del ctx
        if not self.items:
            return [InstructionPart(content=TODO_SYSTEM_PROMPT, dynamic=True)]

        body = strings.join((f"- {todo.text}" for todo in self.items), sep="\n")
        text = strings.Mask("""
            {system_prompt}

            {state_start}
            {body}
            {state_end}
        """).format(
            system_prompt=TODO_SYSTEM_PROMPT,
            state_start=TODO_STATE_START,
            body=body,
            state_end=TODO_STATE_END,
        )

        return [InstructionPart(content=text, dynamic=True)]
