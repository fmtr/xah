from pydantic import Field
from corio import strings
from corio.function import cp
from corio.iterator import IterDiffer, ilist
from xah.class_collections import classes
from xah.options.base import Policy
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.toolset import Toolset


class Activate(Tool):
    """Activate toolsets by ID."""

    ids: list[str] = Field(description="Toolset IDs.")
    reason: str = Field(description="A very short reason to justify why the tool is needed, and why your goal cannot be achieved using existing tools.")

    @classes
    def Validators(cls):
        return [ApproveRequestables]

    @cp
    def permitted(self):
        return self.ctx.deps.toolsets.permitted.name

    @cp
    def valids(self) -> set[str]:
        return IterDiffer(before=self.permitted.keys(), after=self.ids).same

    @cp
    def invalids(self) -> set[str]:
        return IterDiffer(before=self.permitted.keys(), after=self.ids).added

    @cp
    def duplicates(self) -> set[str]:
        activated = self.ctx.deps.toolsets.activated.name
        return IterDiffer(before=activated.keys(), after=self.ids).same

    async def run(self) -> str:
        if self.invalids:
            invalids_text = strings.join_natural(
                sorted(self.invalids), mask=strings.MASK_QUOTE
            )
            message = strings.trim(f"""
                The following toolset IDs do not exist: {invalids_text}.
                You can use the List tool to check available toolset IDs.
            """)
            self.feedback(message)

        permitted = self.permitted
        duplicates = self.duplicates
        for toolset_id in self.valids:
            toolset = permitted[toolset_id]
            if not toolset.activated:
                self.toolset.toolsets.append(type(toolset))
            toolset.activated = True

        if duplicates:
            names = strings.join_natural(
                sorted(duplicates), mask=strings.MASK_QUOTE
            )
            message = strings.trim(f"""
                The following toolsets were already activated: {names}.
                They will stay activated until further notice. You do not need to activate tools again for every turn.
            """)
            self.feedback(message)

        activateds_text = strings.join_natural(sorted(self.valids), mask=strings.MASK_QUOTE)
        return f"The following toolsets have been activated: {activateds_text}"


class ApproveRequestables(Activate):

    @cp
    def requesteds(self)->ilist[Toolset]:
        return ilist(
            self.permitted[toolset_id]
            for toolset_id in self.valids
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
        self.validation.messages.approval.append(msg)

    async def after_approval(self):
        for toolset_id in self.valids:
            toolset = self.permitted[toolset_id]
            toolset.options.cls[Policy].current_value = Policy.Policies.APPROVAL
        await self.ctx.deps.update_config()
