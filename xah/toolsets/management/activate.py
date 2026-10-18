from pydantic import Field
from pydantic_ai import ModelRetry

from corio import strings
from corio.function import cp
from corio.iterator import IterDiffer, ilist
from xah.class_collections import classes
from xah.options.base import Policy
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.toolset import Toolset


class Activate(Tool):
    """Activate or deactivate toolsets by ID."""

    ids: list[str] = Field(description="Toolset IDs.")
    activate: bool = Field(description="Whether to activate or deactivate the selected toolsets.")
    reason: str = Field(description="A very short reason to justify why the tool is needed, and why your goal cannot be achieved using existing tools.")

    @classes
    def Validators(cls):
        return [ValidIDs, ApproveRequestables]

    async def run(self)->str:
        activateds=[]
        for toolset_id in self.ids:
            toolset = self.ctx.deps.toolsets.permitted.name[toolset_id]
            if self.activate and toolset.activated:
                continue
            if toolset.IS_MANAGEMENT and not self.activate:
                self.validation.messages.append(
                    f"The {toolset.name} toolset cannot be deactivated."
                )
                continue
            toolset.activated = self.activate
            activateds.append(toolset_id)
            if self.activate:
                self.toolset.toolsets.append(type(toolset))

        activateds= strings.join_natural(sorted(activateds), mask=strings.MASK_QUOTE)
        msg=f'The following toolsets have been activated: {activateds}'
        return msg


class ValidIDs(Activate):
    async def validate(self):
        permitted = self.ctx.deps.toolsets.permitted.name
        diff = IterDiffer(before=permitted.keys(), after=self.ids)
        if diff.added:
            invalid = strings.join_natural(sorted(diff.added), mask=strings.MASK_QUOTE)
            raise ModelRetry(f"Invalid toolset IDs: {invalid}.")


class ApproveRequestables(Activate):

    @cp
    def requesteds(self)->ilist[Toolset]:
        return ilist(
            self.ctx.deps.toolsets.permitted.name[toolset_id]
            for toolset_id in self.ids
        )

    @cp
    def requestables(self)->ilist[Toolset]:
        return ilist(
            toolset for toolset in self.requesteds
            if toolset.options.cls[Policy].value == Policy.Policies.REQUESTABLE
        )

    async def validate(self):

        if not self.requestables:
            return

        names= strings.join_natural(self.requestables.name.keys(), mask=strings.MASK_QUOTE)
        mask= strings.Mask("""
            The following toolsets require approval: {names}
            Reason given for request: {reason}
        """)
        msg=mask.format(names=names, reason=self.reason)
        self.validation.approval = True
        self.validation.messages.append(msg)

    async def post_approval(self):
        for toolset_id in self.ids:
            toolset = self.ctx.deps.toolsets.permitted.name[toolset_id]
            toolset.options.cls[Policy].current_value = Policy.Policies.APPROVAL
        await self.ctx.deps.update_config()
