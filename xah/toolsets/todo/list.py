from collections import Counter
from pydantic import Field
from pydantic_ai.messages import InstructionPart

from corio import strings
from corio.iterator import ilist
from xah.constants import TODO_STATE_END, TODO_STATE_START
from xah.toolsets.base.output import Output
from xah.toolsets.base.projection.base import ProjectionContent
from xah.toolsets.base.tool import Tool
from xah.toolsets.todo.constants import TodoStatus
from xah.toolsets.todo.item import TodoItem

TODO_SYSTEM_PROMPT = strings.trim("""
    ## Task Management

    Use Todo-Read, Todo-Write, and Todo-UpdateStatus. Keep exactly one task in progress.
""")


class TodoList(Output):
    items: ilist[TodoItem] = Field(default_factory=ilist)

    @property
    def summary(self) -> str:
        counts = Counter(todo.todo_status for todo in self.items)
        summary = strings.join((f"{counts[status]} {status}" for status in TodoStatus), sep=", ")
        return f"Summary: {summary}"

    @property
    def all_completed(self) -> bool:
        return bool(self.items) and all(
            todo.todo_status == TodoStatus.COMPLETED for todo in self.items
        )

    @property
    def agent(self) -> str:
        if not self.items:
            return "No todos in the list."

        numbered_items = strings.join(
            (f"{index}. {item.text}" for index, item in enumerate(self.items, 1)),
            sep="\n",
        )
        return strings.trim("Current todos:", numbered_items, self.summary)

    @property
    def content(self) -> list[ProjectionContent]:
        if not self.items:
            return [self.content_block("No todos in the list.")]

        content = [self.content_block(item.text) for item in self.items]
        content.append(self.content_block(self.summary))
        return content

    def feedback_state(self, tool: Tool) -> None:
        if not self.items:
            tool.feedback("No todos are currently defined. Use Todo-Write to create tasks.")
            return
        if self.all_completed:
            tool.feedback("All tasks are completed; respond to the user.")

    @property
    def instructions(self) -> list[InstructionPart]:
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
