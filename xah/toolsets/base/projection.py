from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from acp.schema import ToolCallStatus
from pydantic_acp.projection import ToolProjection as AcpToolProjection

if TYPE_CHECKING:
    from xah.toolsets.base.tool import Tool
    from xah.toolsets.base.toolset import Toolset


class Projection:
    """Provide a concise default title for one tool call."""

    def __init__(self, *, tool_type: type[Tool], toolset_type: type[Toolset]):
        self.tool_type = tool_type
        self.toolset_type = toolset_type

    @property
    def tool_name(self) -> str:
        return self.toolset_type.tool_name(self.tool_type)

    def title(self) -> str:
        return self.tool_name

    def start(
        self,
        *,
        raw_input: Any,
        cwd: Path | None,
    ) -> AcpToolProjection:
        return AcpToolProjection(title=self.title())

    def progress(
        self,
        *,
        raw_input: Any,
        raw_output: Any,
        serialized_output: str,
        status: ToolCallStatus,
        cwd: Path | None,
    ) -> AcpToolProjection:
        return AcpToolProjection(title=self.title(), status=status)


class ToolsetProjectionMap:
    """Route ACP projection calls to a toolset's tools."""

    def __init__(self, toolset: type[Toolset]):
        self.toolset = toolset

    def project_start(
        self,
        tool_name: str,
        *,
        cwd: Path | None = None,
        raw_input: Any = None,
    ) -> AcpToolProjection | None:
        prefix = self.toolset.prefix
        if not tool_name.startswith(prefix):
            return None

        local_name = self.toolset.local_tool_name(tool_name)
        tool_class = self.toolset.Tools.local_name[local_name]
        if tool_class.PROJECTIONS:
            return None

        projection = tool_class.Projection(
            tool_type=tool_class,
            toolset_type=self.toolset,
        )
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
        prefix = self.toolset.prefix
        if not tool_name.startswith(prefix):
            return None

        local_name = self.toolset.local_tool_name(tool_name)
        tool_class = self.toolset.Tools.local_name[local_name]
        if tool_class.PROJECTIONS:
            return None

        projection = tool_class.Projection(
            tool_type=tool_class,
            toolset_type=self.toolset,
        )
        return projection.progress(
            raw_input=raw_input,
            raw_output=raw_output,
            serialized_output=serialized_output,
            status=status,
            cwd=cwd,
        )
