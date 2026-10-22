from dataclasses import dataclass
from typing import ClassVar

from xah.options.path import PathRead, PathWrite, SelectPath


@dataclass(frozen=True)
class Permissions:
    permission: type[SelectPath]

    Read: ClassVar[type[SelectPath]] = PathRead
    Write: ClassVar[type[SelectPath]] = PathWrite
