from typing import ClassVar

from cached_classproperty import cached_classproperty

from xah.constants import PROJECTION_WRITE_TOOL_NAMES
from xah.toolsets.fs.path import PathPermissions, PathTool


class Remove(PathTool):
    """Remove one file or directory path."""

    projections: ClassVar = PROJECTION_WRITE_TOOL_NAMES

    @cached_classproperty
    def VALIDATORS(cls):
        return [PathPermissions]

    async def run(self) -> str:
        item_type = "Directory" if self.path.is_dir() else "File"
        if self.path.exists():
            if self.path.is_dir():
                self.path.rmtree()
            else:
                self.path.unlink()
        return f"{item_type} '{self.path}' successfully deleted."
