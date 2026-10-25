from typing import Annotated

from pydantic import Field, model_validator

from corio import Path
from xah.toolsets.base.tool import Tool
from xah.toolsets.fs.permissions import Permissions


class FileTool(Tool):
    path: Annotated[Path, Permissions(Permissions.Read)] = Field(
        description="File path relative to the working directory.",
    )

    @model_validator(mode="after")
    def require_file(self):
        if not self.path.exists():
            raise ValueError(f"File '{self.path}' not found")
        if self.path.is_dir():
            raise ValueError(f"'{self.path}' is a directory")
        return self
