from typing import Annotated

from pydantic import Field, model_validator
from pydantic_ai import ModelRetry

from corio import Path
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.class_collections import classes
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.fs.permissions import Permissions


class Input(InputBase):
    source: Annotated[Path, Permissions(Permissions.Read)] = Field(
        description="Existing file or directory to move or copy.",
    )
    target: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="Destination path.",
    )
    is_copy: bool = Field(default=False, description="Copy the source instead of moving it.")

    @property
    def title(self):
        action = "Copying" if self.is_copy else "Moving"
        return f"{action} `{self.source.name}` to `{self.target.name}`"

    @property
    def projection(self):
        locations = [
            self.tool_location(self.source),
            self.tool_location(self.target),
        ]
        return AcpToolProjection(title=self.title, locations=locations)


class Move(Tool, Input):
    """Move or copy a file or directory."""

    KIND = Kinds.MOVE

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
