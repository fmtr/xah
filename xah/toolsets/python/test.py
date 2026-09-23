from functools import cached_property
from typing import Literal

from pydantic import Field

from corio.shell.dsl import Expression, arg, shell
from xah.toolsets.base.subprocess import SubprocessRunner
from xah.toolsets.base.tool import Tool
from xah.toolsets.python.sig import PythonSig


class TestSig(PythonSig):
    tests: list[str] = Field(
        default_factory=list,
        description="Test paths or pytest node IDs. Leave empty to run the complete suite.",
    )
    verbosity: Literal["normal", "verbose", "quiet"] = Field(
        default="normal",
        description="Test output level.",
    )
    timeout: int | None = Field(default=120, gt=0, description="Maximum execution time in seconds.")


class Test(Tool, SubprocessRunner, TestSig):
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
