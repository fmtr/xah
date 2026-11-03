from xah.toolsets.base.tool import Kinds
from xah.toolsets.fs.path import PathTool


class Mkdir(PathTool):
    """Create one directory path."""

    KIND = Kinds.EDIT

    async def run(self) -> str:
        self.path.mkdirf()
        return f"Created directory '{self.path}'."
