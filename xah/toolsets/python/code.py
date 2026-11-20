from functools import cached_property

from corio.shell import arg, ex
from corio.shell.dsl.expression import Expression
from xah.toolsets.terminal.base import TerminalTool


class PythonCode(TerminalTool):
    """Run a tool-provided Python source fragment in the current environment."""

    @property
    def code_args(self) -> tuple[str, ...]:
        return ()

    @cached_property
    def expression(self) -> Expression:
        return ex.python(-arg.c + self.code, *self.code_args)
