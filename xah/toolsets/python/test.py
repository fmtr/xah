from functools import cached_property
from typing import Literal

from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.input import Input as InputBase

from corio.shell.dsl import Expression, arg, shell
from xah.toolsets.terminal.base import TerminalTool


class Input(InputBase):
    tests: list[str] = Field(default_factory=list, description="Test paths or pytest node IDs. Leave empty to run the complete suite.")
    verbosity: Literal["normal", "verbose", "quiet"] = Field(default="normal", description="Test output level.")

    @property
    def projection(self):
        request = self.request
        count = len(self.tests)
        title = "Run test suite" if not count else f"Run {count} tests"
        return AcpToolProjection(title=title)


class Test(TerminalTool, Input):
    """Run the current repository's test suite."""

    @cached_property
    def expression(self) -> Expression:
        verbosity_options = {
            "normal": [],
            "verbose": [--arg.verbose],
            "quiet": [--arg.quiet],
        }
        return shell.python(
            -arg.m + "pytest",
            *verbosity_options[self.verbosity],
            *self.tests,
        )
