from typing import ClassVar

from cached_classproperty import cached_classproperty
from xah.constants import PROJECTION_WRITE_TOOL_NAMES
from xah.toolsets.fs.path import PathTool


class Mkdir(PathTool):
    """Create one directory path."""

    PROJECTIONS: ClassVar[str] = PROJECTION_WRITE_TOOL_NAMES

    async def run(self) -> str:
        self.path.mkdirf()
        return f"Created directory '{self.path}'."
