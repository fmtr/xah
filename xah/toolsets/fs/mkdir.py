from typing import Annotated

from pydantic import Field

from corio import Path
from xah.class_collections import classes
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.output import Output
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.fs.permissions import Permissions


class MkdirOutput(Output):
    path: Path

    @property
    def agent(self) -> str:
        return f"Created directory '{self.path}'."

    @property
    def content(self):
        return [self.content_block(self.agent)]


class Input(InputBase):
    path: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="Path relative to the working directory.",
    )

    @property
    def title(self):
        return f"Creating directory `{self.path.name}`"

    @property
    def locations(self):
        return [self.tool_location(self.path)]


class Mkdir(Tool, Input):
    """Create one directory path."""

    KIND = Kinds.MOVE

    async def run(self) -> MkdirOutput:
        self.path.mkdirf()
        return MkdirOutput(path=self.path)
