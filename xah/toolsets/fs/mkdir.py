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


class Mkdir(Tool, Input):
    """Create one directory path."""

    KIND = Kinds.EDIT

    async def run(self) -> str:
        self.path.mkdirf()
        return f"Created directory '{self.path}'."
