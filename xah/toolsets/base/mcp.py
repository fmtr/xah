from __future__ import annotations

from typing import Any, ClassVar

from cached_classproperty import cached_classproperty
from corio import Path
from corio.function import cp
from fastmcp import Client
from pydantic import ConfigDict
from pydantic_ai.mcp import MCPToolset

from xah.options import base as options
from xah.toolsets.base.common import ToolsetBase


class ToolsetMCP(ToolsetBase, MCPToolset):
    """An MCP toolset configured through harness settings."""

    model_config = ConfigDict(ignored_types=(cached_classproperty,))
    POLICY: ClassVar[str] = options.Policies.FULL
    SUPPORTS_REQUESTABLE: ClassVar[bool] = False

    URL: ClassVar[Any]
    ID: ClassVar[str | None] = None
    CLIENT_OPTIONS: ClassVar[dict[str, Any]] = {}
    TOOLSET_OPTIONS: ClassVar[dict[str, Any]] = {}

    @cp
    def client(self) -> Client:
        return Client(self.URL, **self.CLIENT_OPTIONS)

    def __init__(
        self,
        settings: Any = None,
        cwd: Path | None = None,
        activated: bool = False,
    ):
        del cwd
        self.settings = settings
        super().__init__(
            self.client,
            id=self.name,
            **self.TOOLSET_OPTIONS,
        )
        self.activated = activated
