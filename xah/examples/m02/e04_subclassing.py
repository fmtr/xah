from random import choice

from xah.examples.m02.e01_tool import AgeTool


# (1)!
class PetTool(AgeTool):
    """Return a randomly chosen pet for a user."""

    # (2)!
    async def run(self):
        pet = choice(["cat", "otter", "axolotl"])
        return f"{self.user} has a {pet} as a pet."
