from dataclasses import dataclass

from acp.schema import ToolCallStatus

from xah.toolsets.base.input import Input
from xah.toolsets.base.projection.input import ProjectionRequestInput


@dataclass
class ProjectionRequestOutput(ProjectionRequestInput):
    input: Input
    serialized_output: str
    status: ToolCallStatus
