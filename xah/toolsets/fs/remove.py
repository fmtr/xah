from typing import ClassVar

from cached_classproperty import cached_classproperty
from xah.constants import PROJECTION_WRITE_TOOL_NAMES
from xah.toolsets.fs.path import PathTool


class Remove(PathTool):
    """Remove one file or directory path."""

    PROJECTIONS: ClassVar[str] = PROJECTION_WRITE_TOOL_NAMES

    async def run(self) -> str:
        item_type = "Directory" if self.path.is_dir() else "File"
        if self.path.exists():
            if self.path.is_dir():
                self.path.rmtree()
            else:
                self.path.unlink()
        return f"{item_type} '{self.path}' successfully deleted."
