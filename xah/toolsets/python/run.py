from functools import cached_property

from cached_classproperty import cached_classproperty
from xah.class_collections import classes
from pydantic import Field
from pydantic_ai import ModelRetry

from corio.shell.dsl import shell
from xah.toolsets.terminal.base import TerminalTool
from xah.toolsets.base.tool import ValidationResult


class Run(TerminalTool):
    """Run Python in the current project, with script paths relative to the working directory."""

    args: list[str] = Field(description="Arguments to pass to Python as plain tokens.")

    @classes
    def Validators(cls):
        return [ValidArguments]

    @cached_property
    def expression(self):
        return shell.python(*self.args)


class ValidArguments(Run):
    async def validate(self, result: ValidationResult):
        if not self.args:
            raise ModelRetry("No arguments provided.")

        if self.args[0].lower() in {"python", "python3"}:
            raise ModelRetry("Do not include Python itself. Pass only arguments to Python.")

        if "-c" in self.args:
            from xah.toolsets.python.run_code import RunCode

            run_code_name = self.toolset.tool_name(RunCode)
            message = f"Use {run_code_name} for a short Python code fragment. Write longer code to a .py file and run that file."
            raise ModelRetry(message)

