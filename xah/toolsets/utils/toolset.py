from cached_classproperty import cached_classproperty

from xah.toolsets.base.toolset import Toolset as Toolset
from xah.toolsets.utils.sleep import Sleep


class Utils(Toolset):
    @cached_classproperty
    def TOOLS(cls):
        return [Sleep]
