from typing import Annotated

from pydantic import Field

from corio import Path
from xah.class_collections import classes
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.output import Output
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.fs.permissions import Permissions


class RemoveOutput(Output):
    path: Path
    item_type: str

    @property
    def agent(self) -> str:
        return f"{self.item_type} '{self.path}' successfully deleted."

    @property
    def content(self):
        return [self.content_block(self.agent)]


class Input(InputBase):
    path: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="Path relative to the working directory.",
    )

    @property
    def title(self):
        return f"Removing `{self.path.name}`"

    @property
    def locations(self):
        return [self.tool_location(self.path)]


class Remove(Tool, Input):
    """Remove one file or directory path."""

    KIND = Kinds.DELETE

    async def run(self) -> RemoveOutput:
        item_type = "Directory" if self.path.is_dir() else "File"
        if self.path.exists():
            if self.path.is_dir():
                self.path.rmtree()
            else:
                self.path.unlink()
        return RemoveOutput(path=self.path, item_type=item_type)
