from functools import cached_property
from math import inf
from typing import ClassVar

from cached_classproperty import cached_classproperty
from xah.class_collections import classes
from pydantic import Field
from corio.function import ccp
from xah.toolsets.base.projection import Projection as ProjectionBase
from xah.toolsets.base.tool import Signature as SignatureBase

from corio.shell.dsl import arg, shell
from xah.toolsets.terminal.base import TerminalTool


class Projection(ProjectionBase):
    def title(self):
        return f"Run Python code: {self.preview(self.sig.code, limit=80)}"


class Signature(SignatureBase):
    code: str = Field(description="Short Python source fragment to execute directly.")


class RunCode(TerminalTool, Signature):
    """Run a short Python source fragment directly, like `python -c`."""

    @ccp
    def Projection(cls):
        return Projection

    @classes
    def Validators(cls):
        return [CodeLength]

    @cached_property
    def expression(self):
        return shell.python(-arg.c + self.code)


class CodeLength(RunCode):
    MAX_CODE_LENGTH: ClassVar[float] = inf

    async def validate(self):
        if len(self.code) > self.MAX_CODE_LENGTH:
            message = f"This tool is limited to {self.MAX_CODE_LENGTH} characters. Write longer code to a .py file and run it with Python."
            self.validation.messages.errors.append(message)
            self.validation.abort = True
