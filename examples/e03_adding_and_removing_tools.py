from random import choice

from xah import Tool

from examples.e02_toolset_and_tool import AgeTool, DemoHarness, UserFactsToolset


class PetTool(Tool):
    """Return a randomly chosen pet for a user."""

    user_name: str

    async def run(self):
        # (2)! Return a result the model can use in its reply.
        pet = choice(["cat", "otter", "axolotl"])
        return f"{self.user_name} has a {pet} as a pet."


# (1)! Change the tools available to the imported DemoHarness.
UserFactsToolset.Tools.append(PetTool)
UserFactsToolset.Tools.remove(AgeTool)


if __name__ == "__main__":
    DemoHarness.launch()
