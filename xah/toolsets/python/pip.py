from functools import cached_property

from pydantic import Field

from corio.shell.dsl import arg, shell
from xah.toolsets.base.subprocess import SubprocessRunner


class Pip(SubprocessRunner):
    """Run pip through the current Python interpreter."""

    args: list[str] = Field(description="Arguments to pass to pip as plain tokens without shell syntax.")

    @cached_property
    def expression(self):
        return shell.python(-arg.m + "pip", *self.args)
