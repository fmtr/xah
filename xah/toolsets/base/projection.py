from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from acp.schema import ContentToolCallContent, TextContentBlock, ToolCallStatus
from corio import Constants, strings, yml
from pydantic import BaseModel
from pydantic_acp.projection import ToolProjection as AcpToolProjection

if TYPE_CHECKING:
    from xah.toolsets.base.tool import Tool
    from xah.toolsets.base.toolset import Toolset


class Projection:
    """Provide default ACP input and output presentation for one tool."""

    MAX_VALUE_CHARS = 120

    def __init__(self, *, tool_type: type[Tool], toolset_type: type[Toolset]):
        self.tool_type = tool_type
        self.toolset_type = toolset_type

    @property
    def tool_name(self) -> str:
        return self.toolset_type.tool_name(self.tool_type)

    def title(
        self,
        raw_input: Any,
        raw_output: Any = None,
        *,
        include_output: bool = False,
    ) -> str:

        parts=[]
        title = self.tool_name

        parts.append(title)

        input_preview = self.render(raw_input)
        parts.append(input_preview)

        if include_output:
            output_preview = self.render(raw_output)
            parts.append(output_preview)

        title=strings.join(parts,sep='\n\n')
        return title

    def render(self, value: Any) -> str:
        return yml.to_yaml(self.truncate_leaves(value))

    def truncate_leaves(self, value: Any) -> Any:
        if isinstance(value, BaseModel):
            value = value.model_dump(mode="json")
        elif is_dataclass(value) and not isinstance(value, type):
            value = asdict(value)

        if isinstance(value, Mapping):
            return {
                key: self.truncate_leaves(item)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self.truncate_leaves(item) for item in value]
        return strings.truncate_mid(str(value), length=self.MAX_VALUE_CHARS)

    def start(
        self,
        *,
        raw_input: Any,
        cwd: Path | None,
    ) -> AcpToolProjection:
        input_text = self.render(raw_input)
        return AcpToolProjection(
            title=self.title(raw_input),
            content=self.text_content(input_text),
        )

    def progress(
        self,
        *,
        raw_input: Any,
        raw_output: Any,
        serialized_output: str,
        status: ToolCallStatus,
        cwd: Path | None,
    ) -> AcpToolProjection:
        output_text = self.render(raw_output)
        return AcpToolProjection(
            title=self.title(raw_input, raw_output, include_output=True),
            content=self.text_content(output_text),
            status=status,
        )

    @staticmethod
    def text_content(text: str) -> list[ContentToolCallContent]:
        return [
            ContentToolCallContent(
                type="content",
                content=TextContentBlock(type="text", text=text),
            ),
        ]


class ToolsetProjectionMap:
    """Route ACP projection calls to the owning tool's presentation."""

    def __init__(self, projections: dict[str, Projection]):
        self.projections = projections

    def project_start(
        self,
        tool_name: str,
        *,
        cwd: Path | None = None,
        raw_input: Any = None,
    ) -> AcpToolProjection | None:
        projection = self.projections.get(tool_name)
        if projection is None:
            return None
        return projection.start(raw_input=raw_input, cwd=cwd)

    def project_progress(
        self,
        tool_name: str,
        *,
        cwd: Path | None = None,
        raw_input: Any = None,
        raw_output: Any = None,
        serialized_output: str,
        status: ToolCallStatus,
    ) -> AcpToolProjection | None:
        projection = self.projections.get(tool_name)
        if projection is None:
            return None
        return projection.progress(
            raw_input=raw_input,
            raw_output=raw_output,
            serialized_output=serialized_output,
            status=status,
            cwd=cwd,
        )
