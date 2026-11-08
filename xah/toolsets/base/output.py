from __future__ import annotations

from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any, Self

from acp.schema import ToolCallLocation, ToolCallStatus
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema
from pydantic_acp.projection import ToolProjection as AcpToolProjection

from corio import Constants, dm, strings
from xah.toolsets.base.projection.base import InputOutputBase, ProjectionContent
from xah.toolsets.base.projection.input import ProjectionRequestInput
from xah.toolsets.base.projection.output import ProjectionRequestOutput

if TYPE_CHECKING:
    from xah.toolsets.base.tool import Tool


class Status(StrEnum):
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class Output(InputOutputBase, dm.Base):
    """Base class for structured tool results and their projections."""

    call_id: SkipJsonSchema[str | None] = Field(default=None, exclude=True)
    request: SkipJsonSchema[ProjectionRequestOutput | None] = Field(
        default=None,
        exclude=True,
    )

    @property
    def agent(self) -> Self:
        return self

    @property
    def output_repr(self) -> str:
        return self.preview(self.serialized_text, limit=100)

    @property
    def title(self) -> str:
        output_repr = self.inline_code(self.output_repr)
        return f"{self.request.input.title} {Constants.ARROW_RIGHT} {output_repr}"

    @property
    def content(self) -> list[ProjectionContent]:
        content = self.content_block(self.code_block(self.serialized_text, language="json"))
        return [content]

    @property
    def locations(self) -> list[ToolCallLocation] | None:
        return self.request.input.locations

    @property
    def status(self) -> ToolCallStatus | None:
        return self.request.status

    @property
    def projection(self) -> AcpToolProjection:
        return AcpToolProjection(
            content=self.content,
            locations=self.locations,
            title=self.title,
            status=self.status,
        )

    @classmethod
    def from_result(cls, result: Any) -> Output:
        if isinstance(result, str):
            return OutputString(output=result)
        return result

    def externalize(self, tool: Tool) -> Any:
        if not tool.EXTERNALIZE_OUTPUT:
            return self.agent

        suffix = "txt" if isinstance(self, OutputString) else "json"
        serialized = self.serialized_text

        if len(serialized) <= tool.toolset.MAX_INLINE_OUTPUT_LENGTH:
            return self.agent

        directory = tool.ctx.deps.artifacts_dir
        directory.mkdirf()
        artifact = directory / f"{tool.call_id}.{suffix}"
        artifact.write_text(serialized)

        return strings.trim(f"""
            Tool produced too much output.
            Use regular file tools to inspect the full output: {artifact}
        """)


class OutputString(Output):
    output: str

    @property
    def agent(self) -> str:
        return self.output

    @property
    def serialized_text(self) -> str:
        return self.output

    @property
    def content(self) -> list[ProjectionContent]:
        return [self.content_block(self.output)]


class InvalidInputOutput(Output):
    """Fallback output used when tool input validation fails."""

    request: SkipJsonSchema[ProjectionRequestInput | None] = Field(
        default=None,
        exclude=True,
    )

    @property
    def title(self) -> str:
        return "[INVALID CALL]"

    @property
    def content(self) -> list[ProjectionContent]:
        text = f"{self.request.tool_name}: {self.request.raw_input}"
        return [self.content_block(text)]

    @property
    def locations(self) -> list[ToolCallLocation] | None:
        return None

    @property
    def status(self) -> ToolCallStatus | None:
        return None

    @property
    def agent(self) -> str:
        return "[INVALID CALL]"


class ProjectionErrorOutput(Output):
    request: SkipJsonSchema[ProjectionRequestInput | ProjectionRequestOutput | None] = Field(
        default=None,
        exclude=True,
    )
    stack_trace: str

    @property
    def title(self) -> str:
        return "[PROJECTION ERROR]"

    @property
    def content(self) -> list[ProjectionContent]:
        stack_trace = self.code_block(self.stack_trace, language="pytb")
        return [self.content_block(stack_trace)]

    @property
    def locations(self) -> list[ToolCallLocation] | None:
        return None

    @property
    def status(self) -> ToolCallStatus | None:
        if isinstance(self.request, ProjectionRequestOutput):
            return self.request.status
        return None
