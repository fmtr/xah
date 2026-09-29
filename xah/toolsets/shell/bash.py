from functools import cached_property

from pydantic import Field

from xah.constants import PROJECTION_BASH_TOOL_NAMES
from corio.shell.dsl import arg, shell
from xah.toolsets.base.subprocess import SubprocessRunner


class Bash(SubprocessRunner):
    """Run a bash shell command in the working directory."""

    shell: str = Field(description="Bash source to execute in the working directory.")

    projections = PROJECTION_BASH_TOOL_NAMES

    @cached_property
    def expression(self):
        return shell.bash(-arg.c + self.shell)
