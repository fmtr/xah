from pydantic import Field
from pydantic.json_schema import SkipJsonSchema
from pydantic_acp.projection import ToolProjection as AcpToolProjection

from corio import dm
from xah.toolsets.base.projection.base import InputOutputBase
from xah.toolsets.base.projection.input import ProjectionRequestInput


class Input(InputOutputBase, dm.Base):
    request: SkipJsonSchema[ProjectionRequestInput | None] = Field(
        default=None,
        exclude=True,
    )

    @property
    def projection(self) -> AcpToolProjection:
        return AcpToolProjection(title=self.request.tool_name)
