from cached_classproperty import cached_classproperty

from xah.options import base as options
from xah.toolsets.base.toolset import Toolset


class Python(Toolset):
    """Python execution, package management, and test tools."""

    POLICY = options.APPROVAL

    @cached_classproperty
    def TOOLS(cls):
        from xah.toolsets.python.pip import Pip
        from xah.toolsets.python.run import Run
        from xah.toolsets.python.run_code import RunCode
        from xah.toolsets.python.test import Test

        return [Pip, Run, RunCode, Test]
