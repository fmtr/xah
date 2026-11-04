from functools import cached_property

from cached_classproperty import cached_classproperty
from xah.class_collections import classes
from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from corio import strings
from corio.function import ccp
from xah.toolsets.base.projection import Projection as ProjectionBase
from xah.toolsets.base.tool import Signature as SignatureBase
from corio.shell.dsl import shell
from xah.toolsets.terminal.base import TerminalTool


class Projection(ProjectionBase):
    def title(self):
        return f"Run Python {strings.join(self.sig.args, sep=' ')}"


class Signature(SignatureBase):
    args: list[str] = Field(description="Arguments to pass to Python as plain tokens.")


class Run(TerminalTool, Signature):
    """Run Python in the current project, with script paths relative to the working directory."""

    @ccp
    def Projection(cls):
        return Projection

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

