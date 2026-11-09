from corio import strings
from xah.toolsets.base.output import Output
from xah.toolsets.todo.item import TodoItem


class TodoOutput(Output):
    items: list[TodoItem]
    message: str
    summary: str = ""

    @property
    def agent(self) -> str:
        parts = [self.message]
        if self.items:
            parts.append(
                strings.join(
                    (f"{index}. {item.text}" for index, item in enumerate(self.items, 1)),
                    sep="\n",
                )
            )
        if self.summary:
            parts.append(self.summary)
        return strings.trim(*parts)

    @property
    def content(self):
        content = [self.content_block(item.text) for item in self.items]
        if self.summary:
            content.append(self.content_block(self.summary))
        if not content:
            content.append(self.content_block(self.message))
        return content


class UpdatedTodoOutput(TodoOutput):
    @property
    def title(self) -> str:
        todo = self.items[0]
        return f"Updated todo `{todo.id}` to `{todo.status}`"
