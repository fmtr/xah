from functools import cached_property

from pydantic import Field

from corio.shell.dsl import arg, shell
from xah.toolsets.base.subprocess import SubprocessRunner
from xah.toolsets.base.tool import Tool


class Pip(Tool, SubprocessRunner):
    """Run pip through the current Python interpreter."""

    args: list[str] = Field(description="Arguments to pass to pip as plain tokens without shell syntax.")
    timeout: int | None = Field(default=120, gt=0, description="Maximum execution time in seconds.")

    @cached_property
    def expression(self):
        return shell.python(-arg.m + "pip", *self.args)
