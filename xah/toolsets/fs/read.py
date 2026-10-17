from typing import Annotated, ClassVar

from pydantic import Field
from pydantic_ai import ModelRetry

from corio import Path, dm, strings
from corio.function import cp
from xah.class_collections import classes
from xah.constants import PROJECTION_READ_TOOL_NAMES
from xah.toolsets.fs.permissions import FileTool, Permissions, PermissionsValidator


class Line(dm.Base):
    raw: str
    num: int
    max: int

    @cp
    def stripped(self) -> str:
        return self.raw.rstrip("\r\n")

    @cp
    def truncation(self) -> strings.Truncation:
        return strings.truncate_mid(
            self.stripped,
            self.max,
            flatten_text=False,
            return_type=strings.Truncation,
        )

    @cp
    def text(self) -> str:
        return self.truncation.text

    @cp
    def is_truncated(self) -> bool:
        return self.truncation.was_truncated


class Read(FileTool):
    """Read file content with line numbers."""

    path: Annotated[Path, Permissions(Permissions.Read)] = Field(
        description="File path relative to the working directory.",
    )
    offset: int = Field(default=0, ge=0, description="Zero-based line offset at which to start reading.")
    limit: int = Field(default=2000, gt=0, description="Maximum number of lines to return.")

    MAX_LINE_LENGTH: ClassVar[int] = 20_000
    MAX_OUTPUT_LENGTH: ClassVar[int] = 50_000
    PROJECTIONS: ClassVar[str] = PROJECTION_READ_TOOL_NAMES

    @classes
    def Validators(cls):
        return [ReadPermissions]

    async def run(self) -> str:
        if not self.path.exists():
            raise ModelRetry(f"Error: File '{self.path}' not found")

        if self.path.is_dir():
            raise ModelRetry(f"Error: '{self.path}' is a directory")

        lines = {}
        truncated_lines = []
        output_length = 0
        total_line_count = 0
        omitted_line_count = 0
        output_limit_reached = False

        with self.path.open(errors="replace") as file:
            for number, raw_line in enumerate(file, 1):
                total_line_count = number
                if number <= self.offset:
                    continue
                if number > self.offset + self.limit:
                    continue
                if output_limit_reached:
                    omitted_line_count += 1
                    continue

                line = Line(raw=raw_line, num=number, max=self.MAX_LINE_LENGTH)
                if line.is_truncated:
                    truncated_lines.append(line.num)

                if output_length + len(line.text) > self.MAX_OUTPUT_LENGTH:
                    output_limit_reached = True
                    omitted_line_count += 1
                    continue

                lines[line.num] = line
                output_length += len(line.text)

        if self.offset >= total_line_count:
            line_count = strings.suffix_plural(total_line_count, "line")
            message = strings.Mask(
                "Offset {offset} exceeds the file length of {line_count}; no lines were shown."
            ).format(offset=self.offset, line_count=line_count)
            self.feedback(str(message))

        width = len(str(total_line_count))
        output = "\n".join(
            f"{number:0{width}d}:{line.text}"
            for number, line in lines.items()
        )

        if truncated_lines:
            line_numbers = strings.join_natural(str(number) for number in truncated_lines)
            line_count = strings.suffix_plural(len(truncated_lines), "line")
            message = strings.Mask(
                "{line_count} ({line_numbers}) exceeded the per-line display limit; truncation was applied."
            ).format(line_count=line_count, line_numbers=line_numbers)
            self.feedback(str(message))

        if output_limit_reached:
            line_count = strings.suffix_plural(omitted_line_count, "line")
            message = strings.Mask(
                "Not all lines were shown because the file contains extremely long lines; "
                "{line_count} were omitted."
            ).format(line_count=line_count)
            self.feedback(str(message))
            omitted = strings.suffix_plural(omitted_line_count, "line")
            return strings.trim(output, f"# ... ({omitted} remaining)")

        remaining = total_line_count - (self.offset + self.limit)
        if remaining <= 0:
            return output

        remaining_count = strings.suffix_plural(remaining, "line")
        return strings.trim(output, f"# ... ({remaining_count} remaining)")


class ReadPermissions(PermissionsValidator, Read):
    pass
