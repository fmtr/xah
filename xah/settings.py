import asyncio
from functools import cached_property
from pathlib import Path

from pydantic_acp import host
from typing import ClassVar, Self

from acpremote import TransportOptions
from cached_classproperty import cached_classproperty
from pydantic_settings import CliSubCommand

from corio import dm, PackagePaths
from corio import sets
from corio.logs import logger

from xah.paths import paths


class PathAgent(dm.Base):
    paths: ClassVar[PackagePaths] = paths
    home: Path|None = None
    agents_dir: str = ".agents"
    agents_name: str = "AGENTS.md"
    skills_dir: str = "skills"
    agents: Path | None = None

    def model_post_init(self, __context):
        self.home = (self.home or Path(f"~/.{paths.name}")).expanduser()
        if not self.home.exists():
            logger.warning(f"Creating missing agent home directory: {self.home}")
            self.home.mkdir(parents=True)
        self.agents = self.agents or self.home / self.agents_dir

    @cached_property
    def skills(self) -> Path:
        return self.agents / self.skills_dir

    @cached_property
    def sessions(self) -> Path:
        return self.home / "sessions"


class Acp(dm.Base):
    url: str

    def run(self):
        from xah.server.acp.proxy import Proxy
        from acp import run_agent

        agent = Proxy(
            url=self.url,
            options=TransportOptions(host_ownership="client_passthrough"),
        )
        return asyncio.run(run_agent(agent))




class Settings(sets.Base, cli_parse_args=True):
    paths = paths
    acp: CliSubCommand[Acp]
    path: PathAgent = PathAgent()
    port: int|None = None
    host: str='localhost'
    harness_type: ClassVar

    def model_post_init(self, __context):
        self.port = self.port or self.paths.metadata.port + 8000

    @cached_classproperty
    def PathAgent(self) -> type[PathAgent]:
        return PathAgent

    @classmethod
    def subclass(cls, paths: PackagePaths) -> type[Self]:

        package_paths = paths

        class PackagePath(cls.PathAgent):
            paths = package_paths

        class Settings(super().subclass(paths=package_paths)):
            path: PackagePath = PackagePath()

        return Settings
