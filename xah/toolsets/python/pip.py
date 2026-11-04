from functools import cached_property

from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from corio import strings
from corio.function import ccp
from xah.toolsets.base.projection import Projection as ProjectionBase
from xah.toolsets.base.tool import Signature as SignatureBase

from corio.shell.dsl import arg, shell
from xah.toolsets.terminal.base import TerminalTool


class Projection(ProjectionBase):
    def title(self):
        return f"Pip {strings.join(self.sig.args, sep=' ')}"


class Signature(SignatureBase):
    args: list[str] = Field(description="Arguments to pass to pip as plain tokens without shell syntax.")


class Pip(TerminalTool, Signature):
    """Run pip through the current Python interpreter."""

    @ccp
    def Projection(cls):
        return Projection

    @cached_property
    def expression(self):
        return shell.python(-arg.m + "pip", *self.args)
