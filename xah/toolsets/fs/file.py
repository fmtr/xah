from pydantic import model_validator

from xah.toolsets.base.tool import Tool


class FileTool(Tool):
    @model_validator(mode="after")
    def require_file(self):
        if not self.path.exists():
            raise ValueError(f"File '{self.path}' not found")
        if self.path.is_dir():
            raise ValueError(f"'{self.path}' is a directory")
        return self
