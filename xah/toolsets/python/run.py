from functools import cached_property

from cached_classproperty import cached_classproperty
from pydantic import Field
from pydantic_ai import ModelRetry

from corio.iterator import ilist
from corio.shell.dsl import shell
from xah.toolsets.base.subprocess import SubprocessRunner
from xah.toolsets.base.tool import Tool


class Run(Tool, SubprocessRunner):
    """Run Python in the current project, with script paths relative to the working directory."""

    args: list[str] = Field(description="Arguments to pass to Python as plain tokens.")
    timeout: int | None = Field(default=120, gt=0, description="Maximum execution time in seconds.")

    @cached_classproperty
    def VALIDATORS(cls):
        return ilist([ValidArguments])

    @cached_property
    def expression(self):
        return shell.python(*self.args)


class ValidArguments(Run):
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

            run_code_name = self.toolset.tool_name(RunCode)
            message = f"Use {run_code_name} for a short Python code fragment. Write longer code to a .py file and run that file."
            raise ModelRetry(message)

        return []
