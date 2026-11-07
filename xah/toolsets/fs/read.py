from typing import Annotated, ClassVar

from acp.schema import FileEditToolCallContent, ToolCallLocation
from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from pydantic_ai import ModelRetry

from corio import Path, dm, strings
from corio.function import ccp, cp
from xah.class_collections import classes
from xah.toolsets.base.output import OutputString, ProjectionRequest
from xah.toolsets.base.tool import Input as InputBase, Kinds
from xah.toolsets.fs.file import FileTool
from xah.toolsets.fs.permissions import Permissions


class FileReadOutput(OutputString):

    def get_projection(self, request: ProjectionRequest):
        path = str(request.input.path)
        return AcpToolProjection(
            content=[FileEditToolCallContent(type="diff", path=path, old_text="", new_text=self.output)],
            locations=[ToolCallLocation(path=path)],
            title=request.tool_name,
            status=request.status,
        )


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


class Input(InputBase):
    def get_projection(self, request):
        return AcpToolProjection(title=f"Read {self.preview(str(self.path), limit=80)}")

    path: Annotated[Path, Permissions(Permissions.Read)] = Field(
        description="File path relative to the working directory.",
    )
    offset: int = Field(
        default=0,
        description="Zero-based line offset. To read the tail, use negative values, e.g. -10 returns the last 10 lines.",
    )
    limit: int = Field(
        default=50,
        gt=0,
        le=500,
        description="Maximum number of lines to return.",
    )


class Read(FileTool, Input):
    """Read file content with line numbers."""

    KIND = Kinds.READ

    MAX_LINE_LENGTH: ClassVar[int] = 20_000
    MAX_OUTPUT_LENGTH: ClassVar[int] = 50_000
    EXTERNALIZE_OUTPUT: ClassVar[bool] = False

    async def run(self) -> str:
        with self.path.open(errors="replace") as file:
            total_line_count = sum(1 for _ in file)

        start_offset = self.offset
        if self.offset < 0:
            start_offset = max(total_line_count + self.offset, 0)

        if self.offset >= total_line_count and self.offset >= 0:
            line_count = strings.suffix_plural(total_line_count, "line")
            message = f"Offset {self.offset} exceeds the file length of {line_count}."
            raise ModelRetry(message)

        lines = {}
        truncated_lines = []
        output_length = 0
        output_limit_reached = False
        omitted_line_count = 0

        with self.path.open(errors="replace") as file:
            for number, raw_line in enumerate(file, 1):
                if number <= start_offset:
                    continue
                if number > start_offset + self.limit:
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

        width = len(str(total_line_count)) or 1
        output = "\n".join(
            f"{number:0{width}d}:{line.text}"
            for number, line in lines.items()
        )

        if truncated_lines:
            line_numbers = strings.join_natural(str(number) for number in truncated_lines)
            line_count = strings.suffix_plural(len(truncated_lines), "line")
            message = strings.Mask("{line_count} ({line_numbers}) exceeded the per-line display limit; truncation was applied.").format(line_count=line_count, line_numbers=line_numbers)
            self.feedback(str(message))

        if output_limit_reached:
            line_count = strings.suffix_plural(omitted_line_count, "line")
            message = strings.Mask("Not all lines were shown because the file contains extremely long lines; {line_count} were omitted.").format(line_count=line_count)
            self.feedback(str(message))
            return FileReadOutput(output=output)

        remaining = total_line_count - (start_offset + self.limit)
        if remaining <= 0:
            return FileReadOutput(output=output)

        remaining_count = strings.suffix_plural(remaining, "line")
        self.feedback(f"The file contains {remaining_count} beyond the displayed range.")
        return FileReadOutput(output=output)
