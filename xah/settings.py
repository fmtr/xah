import asyncio
from functools import cached_property
from pathlib import Path
from typing import ClassVar

from acpremote import TransportOptions
from cached_classproperty import cached_classproperty
from pydantic_settings import CliSubCommand

from corio import dm
from corio import sets
from corio.logs import logger

from xah.paths import paths


class PathAgent(dm.Base):
    home: Path = Path(f"~/.{paths.name}")
    agents_dir: str = ".agents"
    agents_name: str = "AGENTS.md"
    skills_dir: str = "skills"
    agents: Path | None = None

    def model_post_init(self, __context):
        self.home = self.home.expanduser()
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
        from xah.acp.proxy import Proxy
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
    port: int = 8000 + paths.metadata.port
    host: str='localhost'
    harness_type: ClassVar

    @cached_classproperty
    def harness_type(cls):
        from xah.harness.base import HarnessBase

        return HarnessBase

    def run(self):
        super().run()

        return self.harness_type.launch(settings=self)
