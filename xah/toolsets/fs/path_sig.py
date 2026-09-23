from typing import Annotated
from pydantic import Field
from corio import Path
from xah.toolsets.fs.sig import FileSig, PATH_WRITE, Permissions, PermissionsValidator


class PathSig(FileSig):
    path: Annotated[Path, Permissions(PATH_WRITE)] = Field(
        description="Path relative to the working directory.",
    )


class PathPermissions(PermissionsValidator, PathSig):
    pass
