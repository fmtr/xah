from typing import Annotated

from pydantic import Field

from corio import Path
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.class_collections import classes
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.fs.permissions import Permissions


class Input(InputBase):
    path: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="Path relative to the working directory.",
    )

    @property
    def projection(self):
        request = self.request
        return AcpToolProjection(title=request.tool_name)


class Remove(Tool, Input):
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
