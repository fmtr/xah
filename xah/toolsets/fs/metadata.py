import grp
import pwd
from datetime import datetime, timezone
from enum import StrEnum, auto
from stat import filemode
from typing import Annotated

from pydantic import Field

from corio import Path, strings
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.output import Output
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.fs.permissions import Permissions


class FileType(StrEnum):
    DIRECTORY = auto()
    FILE = auto()
    OTHER = auto()


class MetadataOutput(Output):
    file_type: FileType
    size_bytes: int
    owner: str
    owner_id: int
    group: str
    group_id: int
    permissions: str
    modified_at: datetime

    @property
    def agent(self) -> str:
        return strings.trim(f"""
            Type: {self.file_type}
            Size: {self.size_bytes} bytes
            Owner: {self.owner} (uid {self.owner_id})
            Group: {self.group} (gid {self.group_id})
            Permissions: {self.permissions}
            Modified: {self.modified_at.isoformat()}
        """)

    @property
    def content(self):
        return [self.content_block(self.agent)]


class Input(InputBase):
    path: Annotated[Path, Permissions(Permissions.Read)] = Field(
        description="File or directory path relative to the working directory.",
    )

    @property
    def title(self):
        return f"Reading filesystem metadata for `{self.path.name}`"

    @property
    def locations(self):
        return [self.tool_location(self.path)]


class Metadata(Tool, Input):
    """Get metadata for a file or directory."""

    KIND = Kinds.READ

    @property
    def file_type(self) -> FileType:
        if self.path.is_dir():
            return FileType.DIRECTORY
        if self.path.is_file():
            return FileType.FILE
        return FileType.OTHER

    async def run(self) -> MetadataOutput:
        metadata = self.path.stat()
        owner = pwd.getpwuid(metadata.st_uid)
        group = grp.getgrgid(metadata.st_gid)
        modified_at = datetime.fromtimestamp(metadata.st_mtime, tz=timezone.utc)

        return MetadataOutput(
            file_type=self.file_type,
            size_bytes=metadata.st_size,
            owner=owner.pw_name,
            owner_id=metadata.st_uid,
            group=group.gr_name,
            group_id=metadata.st_gid,
            permissions=filemode(metadata.st_mode)[1:],
            modified_at=modified_at,
        )
