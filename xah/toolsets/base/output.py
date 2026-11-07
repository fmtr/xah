from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any

from acp.schema import (
    ContentToolCallContent,
    TextContentBlock,
    ToolCallStatus,
)
from pydantic_acp.projection import ToolProjection as AcpToolProjection

from corio import Path, dm, jsn, strings

if TYPE_CHECKING:
    from xah.toolsets.base.tool import Input, Tool
    from xah.toolsets.base.toolset import Toolset


class Status(StrEnum):
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass
class ProjectionRequest:
    tool_cls: type[Tool]
    toolset_cls: type[Toolset]
    raw_input: Any = None
    input: Input | None = None
    cwd: Path | None = None
    serialized_output: str | None = None
    status: ToolCallStatus | None = None

    @property
    def tool_name(self) -> str:
        return self.toolset_cls.get_name(self.tool_cls)


class ProjectionSupport:
    @staticmethod
    def content_block(text: str) -> ContentToolCallContent:
        return ContentToolCallContent(
            type="content",
            content=TextContentBlock(type="text", text=text),
        )

    @staticmethod
    def code_block(text: str, *, language: str | None = None) -> str:
        fence = f"```{language or ''}"
        return f"{fence}\n{text}\n```"

    @staticmethod
    def preview(text: str, *, limit: int) -> str:
        return strings.truncate_mid(text, limit, flatten_text=True)


class Output(ProjectionSupport, dm.Base):
    """Base class for structured tool results and their projections."""

    @classmethod
    def from_result(cls, result: Any) -> Output:
        if isinstance(result, str):
            return OutputString(output=result)
        return result

    def get_agent(self) -> Any:
        return self.model_dump(mode="json")

    def get_projection(self, request: ProjectionRequest) -> AcpToolProjection | None:
        content = None
        if request.serialized_output:
            content = [self.content_block(request.serialized_output)]
        return AcpToolProjection(content=content, title=request.tool_name, status=request.status)

    def serialize(self) -> Any:
        return self.model_dump(mode="json")

    def serialize_text(self) -> str:
        return jsn.to_json(self.serialize())

    def externalize(self, tool: Tool) -> Any:
        if not tool.EXTERNALIZE_OUTPUT:
            return self.get_agent()

        if isinstance(self, OutputString):
            suffix = "txt"
            serialized = self.output
        else:
            suffix = "json"
            serialized = self.serialize_text()

        if len(serialized) <= tool.toolset.MAX_INLINE_OUTPUT_LENGTH:
            return self.get_agent()

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

    def get_agent(self) -> str:
        return self.output

    def get_projection(self, request: ProjectionRequest) -> AcpToolProjection:
        return AcpToolProjection(
            content=[self.content_block(self.output)],
            title=request.tool_name,
            status=request.status,
        )


class InvalidInputOutput(Output):
    """Fallback output used when tool input validation fails."""

    def get_projection(self, request: ProjectionRequest) -> AcpToolProjection:
        text = f"{request.tool_name}: {request.raw_input}"
        content = TextContentBlock(type="text", text=text)
        return AcpToolProjection(
            title="[INVALID CALL]",
            content=[ContentToolCallContent(type="content", content=content)],
            status=request.status,
        )

    def get_agent(self) -> str:
        return "[INVALID CALL]"
