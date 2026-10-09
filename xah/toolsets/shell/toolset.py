from cached_classproperty import cached_classproperty

from xah.options import base as options
from xah.toolsets.base.toolset import Toolset


class Shell(Toolset):
    """Shell execution tools."""

    POLICY = options.DISABLED

    @cached_classproperty
    def TOOLS(cls):
        from xah.toolsets.shell.run import Run

        return [Run]
