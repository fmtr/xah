from pydantic import Field

from xah.toolsets.base.tool import Tool


class Activate(Tool):
    """Activate or deactivate toolsets by ID."""

    ids: list[str] = Field(description="Toolset IDs.")
    activate: bool = Field(description="Whether to activate or deactivate the selected toolsets.")

    async def run(self):
        for toolset_id in self.ids:
            toolset = self.ctx.deps.toolsets.permitted.name[toolset_id]
            if toolset.IS_MANAGEMENT and not self.activate:
                self.validation.messages.append(
                    f"The {toolset.name} toolset cannot be deactivated."
                )
                continue
            toolset.activated = self.activate
