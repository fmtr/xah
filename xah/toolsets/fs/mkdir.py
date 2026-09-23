from typing import ClassVar

from cached_classproperty import cached_classproperty

from corio.iterator import ilist
from xah.constants import PROJECTION_WRITE_TOOL_NAMES
from xah.toolsets.fs.path_sig import PathPermissions, PathTool


class Mkdir(PathTool):
    """Create one directory path."""

    projections: ClassVar = PROJECTION_WRITE_TOOL_NAMES

    @cached_classproperty
    def VALIDATORS(cls):
        return ilist([PathPermissions])

    async def run(self) -> str:
        self.path.mkdirf()
        return f"Created directory '{self.path}'."
