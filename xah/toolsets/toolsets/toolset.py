from xah.class_collections import classes
from xah.toolsets.base.toolset import Toolset


class Toolsets(Toolset):
    """Toolset management toolset."""

    IS_MANAGEMENT = True

    @classes
    def Tools(cls):
        from xah.toolsets.toolsets.activate import Activate
        from xah.toolsets.toolsets.list import List

        return [List, Activate]
