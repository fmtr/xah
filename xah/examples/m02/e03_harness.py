from xah import Harness, classes
from xah.examples.m02.e02_toolset import UserFactsToolset


class DemoHarness(Harness):
    instructions = "Use the tools to tell the user facts about themself."

    @classes
    def Toolsets(cls):
        # (1)!
        return [UserFactsToolset]


if __name__ == "__main__":
    DemoHarness.launch()
