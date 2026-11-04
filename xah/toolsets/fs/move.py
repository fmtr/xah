from typing import Annotated

from pydantic import Field, model_validator
from pydantic_ai import ModelRetry

from corio import Path
from corio.function import ccp
from xah.class_collections import classes
from xah.toolsets.base.projection import NoFileProjection
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase, Tool
from xah.toolsets.fs.permissions import Permissions


class Projection(NoFileProjection):
    pass


class Signature(SignatureBase):
    source: Annotated[Path, Permissions(Permissions.Read)] = Field(
        description="Existing file or directory to move or copy.",
    )
    target: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="Destination path.",
    )
    is_copy: bool = Field(default=False, description="Copy the source instead of moving it.")


class Move(Tool, Signature):
    """Move or copy a file or directory."""

    KIND = Kinds.MOVE

    @ccp
    def Projection(cls):
        return Projection

    @model_validator(mode="after")
    def resolve_move_source(self):
        if not self.is_copy:
            self.source = self.resolve(self.source, Permissions(Permissions.Write))
        return self

    async def run(self) -> str:
        if self.is_copy:
            operation = self.source.copy
            action = "Copied"
        else:
            operation = self.source.move
            action = "Moved"

        try:
            operation(self.target)
        except OSError as error:
            raise ModelRetry(str(error)) from error

        return f"{action} '{self.source}' to '{self.target}'."
