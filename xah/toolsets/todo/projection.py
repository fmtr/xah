from pydantic_acp.projection import ToolProjection as AcpToolProjection

from xah.toolsets.base.projection import Projection as ProjectionBase, Status


class TodoProjection(ProjectionBase):
    def progress(self):
        if self.status != Status.COMPLETED:
            return None
        return AcpToolProjection(content=[self.content(self.output_text)])
