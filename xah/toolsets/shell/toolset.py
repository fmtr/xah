from cached_classproperty import cached_classproperty

from corio.iterator import ilist
from xah.options import base as options
from xah.toolsets.base.toolset import Base


class Shell(Base):
    """Shell execution tools."""

    POLICY = options.DISABLED

    @cached_classproperty
    def TOOLS(cls):
        from xah.toolsets.shell.bash import Bash

        return ilist([Bash])
