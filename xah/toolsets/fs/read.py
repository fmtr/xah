from typing import Annotated, ClassVar

from pydantic import Field
from pydantic_ai import ModelRetry

from corio import Path, strings
from xah.constants import PROJECTION_READ_TOOL_NAMES
from xah.toolsets.base.tool import Tool
from xah.toolsets.fs.sig import FileSig, PATH_READ, Permissions, PermissionsValidator


class ReadSig(FileSig):
    path: Annotated[Path, Permissions(PATH_READ)] = Field(
        description="File path relative to the working directory.",
    )
    offset: int = Field(default=0, ge=0, description="Zero-based line offset at which to start reading.")
    limit: int = Field(default=2000, gt=0, description="Maximum number of lines to return.")


class ReadPermissions(PermissionsValidator, ReadSig):
    pass


class Read(Tool, ReadSig):
    """Read file content with line numbers."""

    projections: ClassVar = PROJECTION_READ_TOOL_NAMES
    VALIDATORS: ClassVar = (ReadPermissions,)

    async def run(self) -> str:
        if not self.path.exists():
            raise ModelRetry(f"Error: File '{self.path}' not found")

        if self.path.is_dir():
            raise ModelRetry(f"Error: '{self.path}' is a directory")

        lines = self.path.read_text(errors="replace").splitlines()

        if self.offset >= len(lines):
            line_count = strings.suffix_plural(len(lines), "line")
            raise ModelRetry(
                f"Error: Offset {self.offset} exceeds file length ({line_count})",
            )

        end = min(self.offset + self.limit, len(lines))
        width = len(str(len(lines)))
        numbered_lines = (
            f"{number:0{width}d}:{line}"
            for number, line in enumerate(
                lines[self.offset:end],
                self.offset + 1,
            )
        )
        output = "\n".join(numbered_lines)

        if end >= len(lines):
            return output

        remaining = len(lines) - end
        return strings.trim(output, f"# ... ({remaining} more lines)")
