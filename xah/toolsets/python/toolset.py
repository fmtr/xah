from cached_classproperty import cached_classproperty

from corio.iterator import ilist
from xah.options import base as options
from xah.toolsets.base.toolset import Base


class Python(Base):
    """Python execution, package management, and test tools."""

    POLICY = options.APPROVAL

    @cached_classproperty
    def TOOLS(cls):
        from xah.toolsets.python.pip import Pip
        from xah.toolsets.python.run import Run
        from xah.toolsets.python.run_code import RunCode
        from xah.toolsets.python.test import Test

        return ilist([Pip, Run, RunCode, Test])
