from xah.options import base as options
from xah.toolsets.base.toolset import Base
from xah.toolsets.python.pip import Pip
from xah.toolsets.python.run import Run
from xah.toolsets.python.run_code import RunCode
from xah.toolsets.python.test import Test


class Python(Base):
    """Python execution, package management, and test tools."""

    POLICY = options.APPROVAL
    TOOLS = (Pip, Run, RunCode, Test)
