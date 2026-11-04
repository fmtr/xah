from typing import Annotated

from pydantic import Field

from corio import Path
from corio.function import ccp
from xah.class_collections import classes
from xah.toolsets.base.projection import NoFileProjection
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase, Tool
from xah.toolsets.fs.permissions import Permissions


class Projection(NoFileProjection):
    pass


class Signature(SignatureBase):
    path: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="Path relative to the working directory.",
    )


class Remove(Tool, Signature):
    """Remove one file or directory path."""

    KIND = Kinds.DELETE

    @ccp
    def Projection(cls):
        return Projection

    async def run(self) -> str:
        item_type = "Directory" if self.path.is_dir() else "File"
        if self.path.exists():
            if self.path.is_dir():
                self.path.rmtree()
            else:
                self.path.unlink()
        return f"{item_type} '{self.path}' successfully deleted."
