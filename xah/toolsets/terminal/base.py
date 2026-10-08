from functools import cached_property

from pydantic import Field

from xah.toolsets.base.tool import Tool

from xah.toolsets.terminal.terminal import Terminal


class TerminalTool(Tool):
    terminal_id: str = Field(description="Identifier of the background terminal.")

    @cached_property
    def terminal(self) -> Terminal:
        return self.toolset.terminals.id[self.terminal_id]
