from xah.options import base as options
from xah.toolsets.base.toolset import Base
from xah.toolsets.shell.bash import Bash


class Shell(Base):
    """Shell execution tools."""
    POLICY = options.DISABLED
    TOOLS = (Bash,)
