from functools import cached_property
from math import inf
from typing import ClassVar

from cached_classproperty import cached_classproperty
from pydantic import Field
from pydantic_ai import ModelRetry

from corio.shell.dsl import arg, shell
from xah.toolsets.base.subprocess import SubprocessRunner
from xah.toolsets.base.tool import ValidationResult


class RunCode(SubprocessRunner):
    """Run a short Python source fragment directly, like `python -c`."""

    code: str = Field(description="Short Python source fragment to execute directly.")

    @cached_classproperty
    def VALIDATORS(cls):
        return [CodeLength]

    @cached_property
    def expression(self):
        return shell.python(-arg.c + self.code)


class CodeLength(RunCode):
    MAX_CODE_LENGTH: ClassVar[float] = inf

    async def validate(self, result: ValidationResult):
        if len(self.code) > self.MAX_CODE_LENGTH:
            message = f"This tool is limited to {self.MAX_CODE_LENGTH} characters. Write longer code to a .py file and run it with Python."
            raise ModelRetry(message)
