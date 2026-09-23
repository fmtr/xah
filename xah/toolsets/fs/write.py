from typing import Annotated, ClassVar

from pydantic import Field

from corio import Path
from xah.constants import PROJECTION_WRITE_TOOL_NAMES
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.validator import Validator
from xah.toolsets.fs.sig import FileSig, PATH_WRITE, Permissions, PermissionsValidator


class WriteSig(FileSig):
    path: Annotated[Path, Permissions(PATH_WRITE)] = Field(
        description="Destination path relative to the working directory.",
    )
    content: str = Field(description="Complete file content to write.")


class WritePermissions(PermissionsValidator, WriteSig):
    pass


class WriteWarnings(Validator, WriteSig):
    async def validate(self) -> list[str]:
        messages = []

        if self.path.is_file():
            current = self.path.read_text(errors="replace")
            similarity = self.get_sim(current, self.content)

            if similarity:
                message = f"You are overwriting a file with {similarity}% similar content. Use partial reads and edits for small changes."
                messages.append(
                    message,
                )

        return messages


class Write(Tool, WriteSig):
    """Write complete content to a file."""

    VALIDATORS: ClassVar = (WritePermissions, WriteWarnings)
    projections: ClassVar = PROJECTION_WRITE_TOOL_NAMES

    async def run(self) -> str:
        self.path.parent.mkdirf()
        self.path.write_text(self.content)
        return f"Wrote {len(self.content.splitlines())} lines to {self.path}"
