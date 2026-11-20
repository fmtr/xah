from math import inf
from typing import ClassVar

from cached_classproperty import cached_classproperty
from xah.class_collections import classes
from pydantic import Field
from corio.function import ccp
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import ValidationAbort

from xah.toolsets.python.code import PythonCode
from xah.toolsets.terminal.base import TerminalOutput


class RunCodeOutput(TerminalOutput):
    COMMAND_LANGUAGE = "python"

    @property
    def command(self) -> str:
        return self.request.input.code


class Input(InputBase):
    code: str = Field(description="Short Python source fragment to execute directly.")

    @property
    def title(self):
        return f"Running Python code `{self.preview(self.code, limit=20)}`"

    @property
    def content(self):
        return [self.content_block(self.code_block(self.code, language="python"))]


class RunCode(PythonCode, Input):
    """Run a short Python source fragment directly, like `python -c`."""

    @ccp
    def Output(cls) -> type[RunCodeOutput]:
        return RunCodeOutput

    @classes
    def Validators(cls):
        return [CodeLength]


class CodeLength(RunCode):
    MAX_CODE_LENGTH: ClassVar[float] = inf

    async def validate(self):
        if len(self.code) > self.MAX_CODE_LENGTH:
            message = f"This tool is limited to {self.MAX_CODE_LENGTH} characters. Write longer code to a .py file and run it with Python."
            raise ValidationAbort(message)
