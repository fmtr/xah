from typing import Annotated

from pydantic import Field

from corio import Path
from xah.toolsets.fs.sig import FileTool, PATH_WRITE, Permissions, PermissionsValidator


class PathTool(FileTool):
    path: Annotated[Path, Permissions(PATH_WRITE)] = Field(
        description="Path relative to the working directory.",
    )


class PathPermissions(PermissionsValidator, PathTool):
    pass
