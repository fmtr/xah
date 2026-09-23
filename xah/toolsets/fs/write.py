from typing import Annotated, ClassVar

from cached_classproperty import cached_classproperty
from pydantic import Field

from corio import Path
from corio.iterator import ilist
from xah.constants import PROJECTION_WRITE_TOOL_NAMES
from xah.toolsets.base.validator import Validator
from xah.toolsets.fs.sig import FileTool, PATH_WRITE, Permissions, PermissionsValidator


class Write(FileTool):
    """Write complete content to a file."""

    path: Annotated[Path, Permissions(PATH_WRITE)] = Field(
        description="Destination path relative to the working directory.",
    )
    content: str = Field(description="Complete file content to write.")

    projections: ClassVar = PROJECTION_WRITE_TOOL_NAMES

    @cached_classproperty
    def VALIDATORS(cls):
        return ilist([WritePermissions, WriteWarnings])

    async def run(self) -> str:
        self.path.parent.mkdirf()
        self.path.write_text(self.content)
        return f"Wrote {len(self.content.splitlines())} lines to {self.path}"


class WritePermissions(PermissionsValidator, Write):
    pass


class WriteWarnings(Validator, Write):
    async def validate(self) -> list[str]:
        messages = []
        if self.path.is_file():
            current = self.path.read_text(errors="replace")
            similarity = self.get_sim(current, self.content)
            if similarity:
                message = f"You are overwriting a file with {similarity}% similar content. Use partial reads and edits for small changes."
                messages.append(message)
        return messages
