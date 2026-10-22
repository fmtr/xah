from typing import Annotated

from pydantic import Field

from corio import Path
from xah.toolsets.base.tool import Tool
from xah.toolsets.fs.permissions import Permissions


class PathTool(Tool):
    path: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="Path relative to the working directory.",
    )
