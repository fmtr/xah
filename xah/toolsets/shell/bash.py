from functools import cached_property

from cached_classproperty import cached_classproperty
from pydantic import Field

from xah.constants import PROJECTION_BASH_TOOL_NAMES
from corio.shell.dsl import arg, shell
from xah.toolsets.base.subprocess import SubprocessRunner


class Bash(SubprocessRunner):
    """Run a bash shell command in the working directory."""

    shell: str = Field(description="Bash source to execute in the working directory.")

    @cached_classproperty
    def VALIDATORS(cls):
        return [RequiresApproval]

    projections = PROJECTION_BASH_TOOL_NAMES

    @cached_property
    def expression(self):
        return shell.bash(-arg.c + self.shell)


class RequiresApproval(Bash):
    async def validate(self) -> list[str]:
        return ["Approval required"]
