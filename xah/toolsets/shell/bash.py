from functools import cached_property

from corio.shell.dsl import arg, shell
from pydantic import Field

from xah.toolsets.base.subprocess import SubprocessRunner


class Bash(SubprocessRunner):
    """Run a bash shell command in the working directory."""

    shell: str = Field(description="Bash source to execute in the working directory.")

    @cached_property
    def expression(self):
        return shell.bash(-arg.c + self.shell)
