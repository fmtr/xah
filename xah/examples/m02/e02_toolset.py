from xah import Toolset, classes
from xah.examples.m02.e01_tool import AgeTool


class UserFactsToolset(Toolset):
    """Tools for fetching facts about users."""

    @classes
    def Tools(cls):
        # (1)!
        return [AgeTool]
