from typing import ClassVar

from cached_classproperty import cached_classproperty
from xah.class_collections import classes

from xah.constants import PROJECTION_WRITE_TOOL_NAMES
from xah.toolsets.fs.path import PathPermissions, PathTool


class Mkdir(PathTool):
    """Create one directory path."""

    PROJECTIONS: ClassVar[str] = PROJECTION_WRITE_TOOL_NAMES

    @classes
    def Validators(cls):
        return [PathPermissions]

    async def run(self) -> str:
        self.path.mkdirf()
        return f"Created directory '{self.path}'."
