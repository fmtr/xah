from cached_classproperty import cached_classproperty
from pydantic_ai import RunContext
from pydantic_ai.messages import InstructionPart

from corio.function import cp
from corio.iterator import ilist
from xah.toolsets.base.toolset import Toolset

from xah.toolsets.terminal.terminal import Terminal


class Terminals(Toolset):
    """Start and manage background shell commands."""

    def __init__(self, settings, cwd):
        self.shell = settings.shell
        super().__init__(settings=settings, cwd=cwd)



    @cp
    def terminals(self) -> ilist[Terminal]:
        return ilist()

    @cached_classproperty
    def TOOLS(cls):
        from xah.toolsets.terminal.status import Status
        from xah.toolsets.terminal.kill import Kill
        from xah.toolsets.terminal.output import Output
        return [Status, Kill, Output]
