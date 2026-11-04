from functools import cached_property
from typing import Literal

from pydantic import Field
from corio.function import ccp
from xah.toolsets.base.projection import Projection as ProjectionBase
from xah.toolsets.base.tool import Signature as SignatureBase

from corio.shell.dsl import Expression, arg, shell
from xah.toolsets.terminal.base import TerminalTool


class Projection(ProjectionBase):
    def title(self):
        count = len(self.sig.tests)
        return "Run test suite" if not count else f"Run {count} tests"


class Signature(SignatureBase):
    tests: list[str] = Field(default_factory=list, description="Test paths or pytest node IDs. Leave empty to run the complete suite.")
    verbosity: Literal["normal", "verbose", "quiet"] = Field(default="normal", description="Test output level.")


class Test(TerminalTool, Signature):
    """Run the current repository's test suite."""

    @ccp
    def Projection(cls):
        return Projection

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
