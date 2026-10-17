from pydantic import Field
from pydantic_ai import ModelRetry

from corio import strings
from corio.iterator import IterDiffer
from xah.class_collections import classes
from xah.options.base import Policy
from xah.toolsets.base.tool import Tool


class Activate(Tool):
    """Activate or deactivate toolsets by ID."""

    ids: list[str] = Field(description="Toolset IDs.")
    activate: bool = Field(description="Whether to activate or deactivate the selected toolsets.")
    reason: str = Field(description="A very short reason for why you believe the tool is needed.")

    @classes
    def Validators(cls):
        return [ValidIDs, ApproveRequestables]

    async def run(self):
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
            if self.activate:
                self.toolset.toolsets.append(type(toolset))


class ValidIDs(Activate):
    async def validate(self):
        permitted = self.ctx.deps.toolsets.permitted.name
        diff = IterDiffer(before=permitted.keys(), after=self.ids)
        if diff.added:
            invalid = strings.join_natural(sorted(diff.added), mask=strings.MASK_QUOTE)
            raise ModelRetry(f"Invalid toolset IDs: {invalid}.")


class ApproveRequestables(Activate):
    async def validate(self):
        requested_toolsets = [
            self.ctx.deps.toolsets.permitted.name[toolset_id]
            for toolset_id in self.ids
        ]
        requestable = any(
            toolset.options.cls[Policy].value == Policy.Policies.REQUESTABLE
            for toolset in requested_toolsets
        )
        if requestable:
            self.validation.approval = True
            self.validation.messages.append(self.reason)

    async def post_approval(self):
        for toolset_id in self.ids:
            toolset = self.ctx.deps.toolsets.permitted.name[toolset_id]
            toolset.options.cls[Policy].current_value = Policy.Policies.APPROVAL
