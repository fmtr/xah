from typing import Annotated, ClassVar

from cached_classproperty import cached_classproperty
from pydantic import Field

from corio import Path
from xah.constants import PROJECTION_WRITE_TOOL_NAMES
from xah.toolsets.fs.permissions import FileTool, Permissions, PermissionsValidator
from xah.toolsets.fs.similarity import get_similarity


class Write(FileTool):
    """Write complete content to a file."""

    path: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="Destination path relative to the working directory.",
    )
    content: str = Field(description="Complete file content to write.")

    projections: ClassVar = PROJECTION_WRITE_TOOL_NAMES

    @cached_classproperty
    def VALIDATORS(cls):
        return [WritePermissions, WriteWarnings]

    async def run(self) -> str:
        self.path.parent.mkdirf()
        self.path.write_text(self.content)
        return f"Wrote {len(self.content.splitlines())} lines to {self.path}"


class WritePermissions(PermissionsValidator, Write):
    pass


class WriteWarnings(Write):
    async def validate(self) -> list[str]:
        messages = []
        if self.path.is_file():
            current = self.path.read_text(errors="replace")
            similarity = get_similarity(current, self.content)
            if similarity:
                message = f"You are overwriting a file with {similarity}% similar content. Use partial reads and edits for small changes."
                messages.append(message)
        return messages
