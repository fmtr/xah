from functools import cached_property
from math import inf
from typing import ClassVar

from pydantic import Field
from pydantic_ai import ModelRetry

from corio.shell.dsl import arg, shell
from xah.toolsets.base.subprocess import SubprocessRunner
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.validator import Validator
from xah.toolsets.python.sig import PythonSig


class RunCodeSig(PythonSig):
    code: str = Field(description="Short Python source fragment to execute directly.")
    timeout: int | None = Field(default=120, gt=0, description="Maximum execution time in seconds.")


class CodeLength(Validator, RunCodeSig):
    MAX_CODE_LENGTH: ClassVar[float] = inf

    @cached_property
    def enabled(self) -> bool:
        return True

    async def validate(self) -> list[str]:
        if len(self.code) > self.MAX_CODE_LENGTH:
            message = f"This tool is limited to {self.MAX_CODE_LENGTH} characters. Write longer code to a .py file and run it with Python."
            raise ModelRetry(message)
        return []


class RunCode(Tool, SubprocessRunner, RunCodeSig):
    """Run a short Python source fragment directly, like `python -c`."""

    VALIDATORS: ClassVar = (CodeLength,)

    @cached_property
    def expression(self):
        return shell.python(-arg.c + self.code)
