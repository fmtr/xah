from dataclasses import dataclass

from corio import Path, strings
from pydantic_deep import Skill as UpstreamSkill


@dataclass(kw_only=True)
class Skill(UpstreamSkill):
    root: Path | None = None
    is_loaded: bool = False

    @property
    def id(self) -> str:
        if self.root is None:
            return self.name
        return Path(self.uri).relative_to(self.root).as_posix()

    @property
    def text(self) -> str:
        if self.is_loaded:
            return self.content
        return self.description

    @property
    def instruction(self) -> str:
        return strings.trim(f"## {self.id}", self.text)
