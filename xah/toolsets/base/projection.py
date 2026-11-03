from __future__ import annotations

from typing import TYPE_CHECKING, Any

from acp.schema import ToolCallStatus
from pydantic import ValidationError
from pydantic_acp.projection import ToolProjection as AcpToolProjection

from corio import Path
from corio.function import cp

if TYPE_CHECKING:
    from xah.toolsets.base.tool import Signature, Tool
    from xah.toolsets.base.toolset import Toolset


class Projection:
    """Provide a concise default title for one tool call."""

    def __init__(
        self,
        *,
        tool_cls: type[Tool],
        toolset_cls: type[Toolset],
        raw_input: Any = None,
        cwd: Path | None = None,
        raw_output: Any = None,
        serialized_output: str | None = None,
        status: ToolCallStatus | None = None,
    ):
        self.tool_cls = tool_cls
        self.toolset_cls = toolset_cls
        self.raw_input = raw_input
        self.cwd = cwd
        self.raw_output = raw_output
        self.serialized_output = serialized_output
        self.status = status

    @property
    def tool_name(self) -> str:
        return self.toolset_cls.get_name(self.tool_cls)

    @cp
    def sig(self) -> Signature | None:
        signature_class = self.tool_cls.sig
        if signature_class is None:
            return None

        try:
            return signature_class.model_validate(self.raw_input)
        except ValidationError:
            return None

    def title(self) -> str:
        return self.tool_name

    def start(self) -> AcpToolProjection:
        return AcpToolProjection(title=self.title())

    def progress(self) -> AcpToolProjection:
        return AcpToolProjection(title=self.title(), status=self.status)
