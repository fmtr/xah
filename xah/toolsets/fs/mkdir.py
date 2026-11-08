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
    def title(self):
        return f"Creating directory `{self.path.name}`"

    @property
    def projection(self):
        return AcpToolProjection(
            title=self.title,
            locations=[self.tool_location(self.path)],
        )


class Mkdir(Tool, Input):
    """Create one directory path."""

    KIND = Kinds.EDIT

    async def run(self) -> str:
        self.path.mkdirf()
        return f"Created directory '{self.path}'."
