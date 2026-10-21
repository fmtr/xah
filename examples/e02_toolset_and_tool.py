from random import randint

from xah import Harness, Tool, Toolset, classes


class DemoHarness(Harness):
    instructions = "Use the tools to tell the user facts about themself."

    @classes
    def Toolsets(cls):
        # (1)! This replaces the default toolsets with the ones listed here.
        return [UserFactsToolset]


class UserFactsToolset(Toolset):
    """Tools for fetching info about users."""

    @classes
    def Tools(cls):
        # (2)! The toolset exposes each tool class listed here.
        return [AgeTool]


class AgeTool(Tool):
    """Return a randomly generated age for a user."""

    user_name: str

    async def run(self):
        # (3)! The harness runs this method when the model calls AgeTool.
        age = randint(1, 100)
        return f"{self.user_name} is {age} years old."


if __name__ == "__main__":
    DemoHarness.launch()
