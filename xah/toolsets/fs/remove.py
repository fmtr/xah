from xah.toolsets.base.tool import Kinds
from xah.toolsets.fs.path import PathTool


class Remove(PathTool):
    """Remove one file or directory path."""

    KIND = Kinds.DELETE

    async def run(self) -> str:
        item_type = "Directory" if self.path.is_dir() else "File"
        if self.path.exists():
            if self.path.is_dir():
                self.path.rmtree()
            else:
                self.path.unlink()
        return f"{item_type} '{self.path}' successfully deleted."
