from pydantic import model_validator

from corio import Path
from xah.class_collections import classes
from xah.toolsets.base.tool import Tool


class FileTool(Tool):
    @classes
    def Validators(cls):
        return [SecretValidator]

    @model_validator(mode="after")
    def require_file(self):
        if not self.path.exists():
            raise ValueError(f"File '{self.path}' not found")
        if self.path.is_dir():
            raise ValueError(f"'{self.path}' is a directory")
        return self


class SecretValidator(FileTool):
    path: Path

    def is_secret(self) -> bool:
        return any(self.path.match(glob) for glob in self.ctx.deps.settings.path.secrets)

    async def validate(self):
        if not self.is_secret():
            return

        self.validation.approval = True
        self.validation.messages.approval.append(
            f'Accessing secrets file: "{self.path}"'
        )
