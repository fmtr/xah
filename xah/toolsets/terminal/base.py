from functools import cached_property
from typing import ClassVar

from pydantic import Field
from pydantic_ai import RunContext

from corio import strings
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.toolset import Toolset

from xah.toolsets.terminal.terminal import Terminal


class TerminalTool(Tool):
    EVENT: ClassVar[str]
    TAIL_SIZE: ClassVar[int] = 512
    MASK: ClassVar[str] = """
        Terminal `{id}` {event}.

        {summary}

        ```
        {tail}
        ```

        Use the {tool} tool to inspect its full output.
    """
    terminal_id: str = Field(description="Identifier of the background terminal.")

    @classmethod
    def notify(cls, ctx: RunContext, terminal: Terminal) -> None:
        from xah.toolsets.terminal.output import Output

        event = cls.EVENT.format(status=terminal.status)
        message = strings.Mask(cls.MASK).format(
            id=terminal.id,
            event=event,
            summary=terminal.summary,
            tail=terminal.tail(cls.TAIL_SIZE) or "[No New Output]",
            tool=Output.local_name,
        )
        Toolset.feedback(ctx, message)

    @cached_property
    def terminal(self) -> Terminal:
        return self.toolset.terminals.id[self.terminal_id]
