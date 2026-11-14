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

        toolsets = [
            toolset
            for toolset in ctx.deps.toolsets.permitted
            if not toolset.IS_MANAGEMENT
        ]
        activated = [toolset for toolset in toolsets if toolset.activated]
        available = [toolset for toolset in toolsets if not toolset.activated]
        activate_name = self.get_name(Activate)
        active_names = strings.trim(
            *(f"- `{toolset.name}`" for toolset in activated)
        ) or "None."
        available_details = strings.trim(
            *(toolset.info.instruction for toolset in available)
        ) or "None."
        activated_instruction = strings.trim(
            strings.Mask("""
                ## Already Activated Toolsets

                These toolsets are already activated and available. Use their tools directly. **Never call `{activate_name}` for any listed ID again. They remain active for the entire session; do not request activation on future turns.**

                {active_names}
            """).format(
                activate_name=activate_name,
                active_names=active_names,
            )
        )
        available_instruction = strings.trim(
            strings.Mask("""
                ## Available Toolsets

                These toolsets are not yet activated, but are available. Activate one only when you need it, using `{activate_name}`.

                {available_details}
            """).format(
                activate_name=activate_name,
                available_details=available_details,
            )
        )
        return [
            InstructionPart(content=activated_instruction, dynamic=True),
            InstructionPart(content=available_instruction, dynamic=True),
        ]
