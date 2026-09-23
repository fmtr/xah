from xah.constants import PROJECTION_WRITE_TOOL_NAMES
from xah.toolsets.base.tool import Tool
from xah.toolsets.fs.path_sig import PathPermissions, PathSig
from typing import ClassVar


class Remove(Tool, PathSig):
    """Remove one file or directory path."""
    projections: ClassVar = PROJECTION_WRITE_TOOL_NAMES
    VALIDATORS: ClassVar = (PathPermissions,)
    async def run(self) -> str:
        item_type = "Directory" if self.path.is_dir() else "File"
        if self.path.exists():
            if self.path.is_dir():
                self.path.rmtree()
            else:
                self.path.unlink()
        return f"{item_type} '{self.path}' successfully deleted."
