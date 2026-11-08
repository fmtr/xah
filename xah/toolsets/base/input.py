from pydantic import Field
from pydantic.json_schema import SkipJsonSchema
from pydantic_acp.projection import ToolProjection as AcpToolProjection

from corio import dm
from acp.schema import ToolCallLocation
from xah.toolsets.base.projection.base import InputOutputBase, ProjectionContent
from xah.toolsets.base.projection.input import ProjectionRequestInput


class Input(InputOutputBase, dm.Base):
    request: SkipJsonSchema[ProjectionRequestInput | None] = Field(
        default=None,
        exclude=True,
    )

    @property
    def title(self) -> str:
        serialized = self.preview(self.serialized_text, limit=100)
        return f"{self.request.tool_name}({self.inline_code(serialized)})"

    @property
    def content(self) -> list[ProjectionContent] | None:
        return None

    @property
    def locations(self) -> list[ToolCallLocation] | None:
        return None

    @property
    def projection(self) -> AcpToolProjection:
        return AcpToolProjection(
            content=self.content,
            locations=self.locations,
            title=self.title,
        )
