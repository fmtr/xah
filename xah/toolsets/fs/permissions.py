from dataclasses import dataclass
from typing import ClassVar

from xah.options.path import PathRead, PathWrite, SelectPath


@dataclass
class Permissions:
    permission: type[SelectPath]
    must_exist: bool | None = None
    resolve_project: bool = False

    Read: ClassVar[type[SelectPath]] = PathRead
    Write: ClassVar[type[SelectPath]] = PathWrite

    def __post_init__(self) -> None:
        if self.must_exist is None:
            self.must_exist = self.permission is self.Read
