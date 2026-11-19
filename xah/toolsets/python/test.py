from functools import cached_property
from typing import Literal

from pydantic import Field
from corio import strings
from corio.function import ccp
from xah.toolsets.base.input import Input as InputBase

from corio.shell import arg, ex
from corio.shell.dsl.expression import Expression
from xah.toolsets.terminal.base import TerminalOutput, TerminalTool


class TestOutput(TerminalOutput):
    pass


class Input(InputBase):
    tests: list[str] = Field(default_factory=list, description="Test paths or pytest node IDs. Leave empty to run the complete suite.")
    verbosity: Literal["normal", "verbose", "quiet"] = Field(default="normal", description="Test output level.")
    coverage: bool = Field(default=False, description="Collect coverage and show missing lines.")

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

    @property
    def env(self) -> dict[str, str]:
        environment = super().env
        if not self.coverage:
            return environment

        coverage_options = [
            --arg.cov + "xah",
            --arg.cov_report + "term-missing:skip-covered",
        ]
        coverage_settings = " ".join(str(option) for option in coverage_options)
        environment["PYTEST_ADDOPTS"] = coverage_settings
        return environment

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
        return ex.python(
            -arg.m + "pytest",
            *verbosity_options[self.verbosity],
            *self.tests,
        )
