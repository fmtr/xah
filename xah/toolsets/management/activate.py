from pydantic import Field

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
        return [ApproveRequestables]

    async def run(self):
        for toolset_id in self.ids:
            toolset = self.ctx.deps.toolsets.permitted.name[toolset_id]
            if toolset.IS_MANAGEMENT and not self.activate:
                self.validation.messages.append(
                    f"The {toolset.name} toolset cannot be deactivated."
                )
                continue
            toolset.activated = self.activate


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
