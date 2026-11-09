from functools import cached_property

from pydantic import Field
from corio import strings
from corio.function import ccp
from xah.toolsets.base.input import Input as InputBase

from corio.shell.dsl import arg, shell
from xah.toolsets.terminal.base import TerminalOutput, TerminalTool


class PipOutput(TerminalOutput):
    pass


class Input(InputBase):
    args: list[str] = Field(description="Arguments to pass to pip as plain tokens without shell syntax.")

    @property
    def title(self):
        if not self.args:
            return "Running pip"
        args = self.preview(strings.join(self.args, sep=" "), limit=20)
        return f"Running pip `{args}`"

    @property
    def content(self):
        command = strings.join(("python", "-m", "pip", *self.args))
        return [self.content_block(self.code_block(command, language="bash"))]


class Pip(TerminalTool, Input):
    """Run pip through the current Python interpreter."""

    @ccp
    def Output(cls) -> type[PipOutput]:
        return PipOutput

    @cached_property
    def expression(self):
        return shell.python(-arg.m + "pip", *self.args)
