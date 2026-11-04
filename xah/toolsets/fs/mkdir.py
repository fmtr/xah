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


class Mkdir(Tool, Signature):
    """Create one directory path."""

    KIND = Kinds.EDIT

    @ccp
    def Projection(cls):
        return Projection

    async def run(self) -> str:
        self.path.mkdirf()
        return f"Created directory '{self.path}'."
