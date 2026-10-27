from cached_classproperty import cached_classproperty
from pydantic_ai import RunContext
from pydantic_ai.messages import InstructionPart

from corio import strings
from corio.function import cp
from corio.iterator import ilist
from xah.class_collections import classes
from xah.toolsets.base.toolset import Toolset

from xah.toolsets.terminal.terminal import Terminal


class Terminals(Toolset):
    """Start and manage background shell commands."""

    def __init__(self, settings, cwd, activated: bool = True):
        self.shell = settings.shell
        super().__init__(settings=settings, cwd=cwd, activated=activated)

    @cp
    def statuses(self)->str:
        lines = [
            f"{status}: {', '.join(terminal.id for terminal in terminals)}"
            for status, terminals in self.terminals.status.items()
        ]
        statuses = "\n".join(lines) or "none"
        return statuses


    async def get_instructions(self, ctx: RunContext) -> list[InstructionPart]:
        from xah.toolsets.fs.toolset import Files
        from xah.toolsets.terminal.status import Status
        from xah.toolsets.utils.toolset import Utils

        text = strings.trim(f"""
            # {self.name}

            {self.statuses}

            Output from longer-running and verbose {self.name} will not be shown inline.
            You must use the relevant tools to manage them.

            - `{self.name}` tools manage the processes themselves, including stopping them early.
            - `{Files.name}` tools monitor output tail, search output, and inspect output files.
            - `{Utils.name}` tools to wait for output. Do not spam the `{Status.local_name}` tool repeatedly.
        """)
        return [InstructionPart(content=text, dynamic=True)]

    @cp
    def terminals(self) -> ilist[Terminal]:
        return ilist()

    @classes
    def Tools(cls):
        from xah.toolsets.terminal.status import Status
        from xah.toolsets.terminal.kill import Kill
        return [Status, Kill]
