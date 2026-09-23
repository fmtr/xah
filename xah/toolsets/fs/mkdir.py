from xah.constants import PROJECTION_WRITE_TOOL_NAMES
from xah.toolsets.base.tool import Tool
from xah.toolsets.fs.path_sig import PathPermissions, PathSig
from typing import ClassVar


class Mkdir(Tool, PathSig):
    """Create one directory path."""
    projections: ClassVar = PROJECTION_WRITE_TOOL_NAMES
    VALIDATORS: ClassVar = (PathPermissions,)
    async def run(self) -> str:
        self.path.mkdirf()
        return f"Created directory '{self.path}'."
