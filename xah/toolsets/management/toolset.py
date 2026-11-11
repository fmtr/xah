from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.messages import InstructionPart

from corio import strings
from corio.function import cp
from corio.iterator import ilist
from xah.class_collections import classes
from xah.toolsets.base.toolset import Toolset


class Management(Toolset):
    """Toolset management toolset."""

    IS_MANAGEMENT = True

    @cp
    def toolsets(self) -> ilist[type[Toolset]]:
        return ilist()

    @classes
    def Tools(cls):
        from xah.toolsets.management.activate import Activate

        return [Activate]

    async def get_instructions(self, ctx: RunContext[Any]) -> list[InstructionPart]:
        from xah.toolsets.management.activate import Activate

        toolsets = ctx.deps.toolsets.permitted
        activate_name = self.get_name(Activate)
        overview = strings.Mask("""
            ## Available Toolsets

            Use `{activate_name}` to activate an inactive toolset. Active toolsets stay enabled; do not reactivate them.
        """).format(activate_name=activate_name)
        overview = strings.trim(overview)
        instructions = [InstructionPart(content=overview, dynamic=True)]
        instructions.extend(
            InstructionPart(content=toolset.info.instruction, dynamic=True)
            for toolset in toolsets
        )
        return instructions
