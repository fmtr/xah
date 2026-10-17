from xah.class_collections import classes
from xah.toolsets.base.toolset import Toolset


class Management(Toolset):
    """Toolset management toolset."""

    IS_MANAGEMENT = True

    @classes
    def Tools(cls):
        from xah.toolsets.management.activate import Activate
        from xah.toolsets.management.list import List

        return [List, Activate]
