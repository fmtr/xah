from typing import Annotated

from pydantic import Field

from corio import Path
from xah.toolsets.fs.permissions import FileTool, Permissions, PermissionsValidator


class PathTool(FileTool):
    path: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="Path relative to the working directory.",
    )


class PathPermissions(PermissionsValidator, PathTool):
    pass
