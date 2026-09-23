from dataclasses import dataclass
from pydantic_deep import Skill as UpstreamSkill
from corio import Path, strings


@dataclass(kw_only=True)
class Skill(UpstreamSkill):
    root: Path | None = None

    @property
    def id(self) -> str:
        if self.root is None:
            return self.name
        return Path(self.uri).relative_to(self.root).as_posix()

    @property
    def text(self) -> str:
        return strings.trim(f"## {self.id}\n{self.content}")

    @property
    def text_description(self) -> str:
        return strings.trim(f"## {self.id}\n{self.description}")
