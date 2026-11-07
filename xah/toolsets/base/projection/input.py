from dataclasses import dataclass
from pathlib import Path


@dataclass
class ProjectionRequestInput:
    tool_cls: type
    toolset_cls: type
    raw_input: object
    cwd: Path | None

    @property
    def tool_name(self) -> str:
        return self.toolset_cls.get_name(self.tool_cls)
