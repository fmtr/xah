from __future__ import annotations

from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any, Self

from acp.schema import ContentToolCallContent, TextContentBlock
from pydantic import Field
from pydantic.json_schema import SkipJsonSchema
from pydantic_acp.projection import ToolProjection as AcpToolProjection

from corio import Constants, dm, jsn, strings
from xah.toolsets.base.projection.base import InputOutputBase
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
    def projection(self) -> AcpToolProjection | None:
        request = self.request
        content = None
        title = request.tool_name
        if request.serialized_output:
            preview = self.preview(request.serialized_output, limit=120)
            title = f"{title} {Constants.ARROW_RIGHT} {preview}"
            content = [self.content_block(request.serialized_output)]
        return AcpToolProjection(content=content, title=title, status=request.status)

    @classmethod
    def from_result(cls, result: Any) -> Output:
        if isinstance(result, str):
            return OutputString(output=result)
        return result

    def serialize(self) -> Any:
        return self.model_dump(mode="json")

    def serialize_text(self) -> str:
        return jsn.to_json(self.serialize())

    def externalize(self, tool: Tool) -> Any:
        if not tool.EXTERNALIZE_OUTPUT:
            return self.agent

        if isinstance(self, OutputString):
            suffix = "txt"
            serialized = self.output
        else:
            suffix = "json"
            serialized = self.serialize_text()

        if len(serialized) <= tool.toolset.MAX_INLINE_OUTPUT_LENGTH:
            return self.agent

        settings = tool.ctx.deps.settings
        directory = tool.ctx.deps.cwd_default / settings.path.home.name / "artifacts"
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
    def projection(self) -> AcpToolProjection:
        request = self.request
        return AcpToolProjection(
            content=[self.content_block(self.output)],
            title=request.tool_name,
            status=request.status,
        )


class InvalidInputOutput(Output):
    """Fallback output used when tool input validation fails."""

    request: SkipJsonSchema[ProjectionRequestInput | None] = Field(
        default=None,
        exclude=True,
    )

    @property
    def projection(self) -> AcpToolProjection:
        request = self.request
        text = f"{request.tool_name}: {request.raw_input}"
        content = TextContentBlock(type="text", text=text)
        return AcpToolProjection(
            title="[INVALID CALL]",
            content=[ContentToolCallContent(type="content", content=content)],
        )

    @property
    def agent(self) -> str:
        return "[INVALID CALL]"
