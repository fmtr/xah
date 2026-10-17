from cached_classproperty import cached_classproperty
from xah.class_collections import classes

from xah.toolsets.base.toolset import Toolset as Toolset
from xah.toolsets.utils.sleep import Sleep


class Utils(Toolset):
    """General-purpose utility tools, including pausing execution for a fixed duration."""

    @classes
    def Tools(cls):
        return [Sleep]
