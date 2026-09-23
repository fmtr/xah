from functools import cached_property
from typing import ClassVar

from pydantic import Field
from pydantic_ai import ModelRetry

from corio.shell.dsl import shell
from xah.toolsets.base.subprocess import SubprocessRunner
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.validator import Validator
from xah.toolsets.python.sig import PythonSig


class RunSig(PythonSig):
    args: list[str] = Field(description="Arguments to pass to Python as plain tokens.")
    timeout: int | None = Field(default=120, gt=0, description="Maximum execution time in seconds.")


class ValidArguments(Validator, RunSig):
    @cached_property
    def enabled(self) -> bool:
        return True

    async def validate(self) -> list[str]:
        if not self.args:
            raise ModelRetry("No arguments provided.")

        if self.args[0].lower() in {"python", "python3"}:
            raise ModelRetry("Do not include Python itself. Pass only arguments to Python.")

        if "-c" in self.args:
            from xah.toolsets.python.run_code import RunCode

            message = f"Use {RunCode.name} for a short Python code fragment. Write longer code to a .py file and run that file."
            raise ModelRetry(message)

        return []


class Run(Tool, SubprocessRunner, RunSig):
    """Run Python in the current project, with script paths relative to the working directory."""

    VALIDATORS: ClassVar = (ValidArguments,)

    @cached_property
    def expression(self):
        return shell.python(*self.args)
