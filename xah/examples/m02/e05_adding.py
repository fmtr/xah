from xah.examples.m02.e01_tool import AgeTool
from xah.examples.m02.e02_toolset import UserFactsToolset
from xah.examples.m02.e03_harness import DemoHarness
from xah.examples.m02.e04_subclassing import PetTool


# (1)!
UserFactsToolset.Tools.append(PetTool)

# (2)!
UserFactsToolset.Tools.remove(AgeTool)


if __name__ == "__main__":
    DemoHarness.launch()
