from functools import cached_property
from typing import Literal

from pydantic import Field
from corio import strings
from corio.function import ccp
from xah.toolsets.base.input import Input as InputBase

from corio.shell.dsl import Expression, arg, shell
from xah.toolsets.terminal.base import TerminalOutput, TerminalTool


class TestOutput(TerminalOutput):
    pass


class Input(InputBase):
    tests: list[str] = Field(default_factory=list, description="Test paths or pytest node IDs. Leave empty to run the complete suite.")
    verbosity: Literal["normal", "verbose", "quiet"] = Field(default="normal", description="Test output level.")

    @property
    def title(self):
        if not self.tests:
            return "Running Python test suite"
        test_count = strings.suffix_plural(len(self.tests), "Python test")
        return f"Running {test_count}"

    @property
    def content(self):
        command = strings.join(("pytest", *self.tests))
        return [self.content_block(self.code_block(command, language="bash"))]


class Test(TerminalTool, Input):
    """Run the current repository's test suite."""

    @ccp
    def Output(cls) -> type[TestOutput]:
        return TestOutput

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
