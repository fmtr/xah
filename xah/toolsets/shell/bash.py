from functools import cached_property
from cached_classproperty import cached_classproperty
from pydantic import Field
from corio.shell.dsl import arg, shell
from xah.toolsets.base.subprocess import SubprocessRunner
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.validator import Validator
from xah.toolsets.shell.sig import ShellSig
from typing import ClassVar


class BashSig(ShellSig):
    shell: str = Field(description="Bash source to execute in the working directory.")
    timeout: int | None = Field(default=120, gt=0, description="Maximum execution time in seconds.")


class RequiresApproval(Validator, BashSig):
    async def validate(self) -> list[str]:
        return ["Approval required"]


class Bash(Tool, SubprocessRunner, BashSig):
    """Run a bash shell command in the working directory."""
    VALIDATORS: ClassVar = (RequiresApproval,)

    @cached_classproperty
    def projections(cls):
        from pydantic_acp import FileSystemProjectionMap
        return FileSystemProjectionMap(bash_tool_names=frozenset({cls.name}), command_arg="shell")

    @cached_property
    def expression(self):
        return shell.bash(-arg.c + self.shell)
