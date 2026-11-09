from functools import cached_property

from cached_classproperty import cached_classproperty
from xah.class_collections import classes
from pydantic import Field
from corio import strings
from corio.function import ccp
from xah.toolsets.base.input import Input as InputBase
from corio.shell.dsl import shell
from xah.toolsets.terminal.base import TerminalOutput, TerminalTool


class PythonRunOutput(TerminalOutput):
    pass


class Input(InputBase):
    args: list[str] = Field(description="Arguments to pass to Python as plain tokens.")

    @property
    def title(self):
        if not self.args:
            return "Running Python"
        args = self.preview(strings.join(self.args, sep=" "), limit=20)
        return f"Running Python `{args}`"

    @property
    def content(self):
        command = strings.join(("python", *self.args))
        return [self.content_block(self.code_block(command, language="bash"))]


class Run(TerminalTool, Input):
    """Run Python in the current project, with script paths relative to the working directory."""

    @ccp
    def Output(cls) -> type[PythonRunOutput]:
        return PythonRunOutput

    @classes
    def Validators(cls):
        return [ValidArguments]

    @cached_property
    def expression(self):
        return shell.python(*self.args)


class ValidArguments(Run):
    async def validate(self):
        if not self.args:
            self.validation.messages.errors.append("No arguments provided.")
            self.validation.abort = True
            return

        if self.args[0].lower() in {"python", "python3"}:
            self.validation.messages.errors.append(
                "Do not include Python itself. Pass only arguments to Python."
            )
            self.validation.abort = True
            return

        if "-c" in self.args:
            from xah.toolsets.python.run_code import RunCode

            run_code_name = self.toolset.get_name(RunCode)
            message = f"Use {run_code_name} for a short Python code fragment. Write longer code to a .py file and run that file."
            self.validation.messages.errors.append(message)
            self.validation.abort = True

