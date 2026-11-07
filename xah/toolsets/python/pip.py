from functools import cached_property

from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from corio import strings
from xah.toolsets.base.tool import Input as InputBase

from corio.shell.dsl import arg, shell
from xah.toolsets.terminal.base import TerminalTool


class Input(InputBase):
    args: list[str] = Field(description="Arguments to pass to pip as plain tokens without shell syntax.")

    def get_projection(self, request):
        title = f"Pip {strings.join(self.args, sep=' ')}"
        return AcpToolProjection(title=title)


class Pip(TerminalTool, Input):
    """Run pip through the current Python interpreter."""

    @cached_property
    def expression(self):
        return shell.python(-arg.m + "pip", *self.args)
