from __future__ import annotations

from typing import Any, ClassVar

from corio.function import cp
from fastmcp import Client
from pydantic_ai.mcp import MCPToolset


class ToolsetMCP(MCPToolset):
    """An MCP toolset configured through harness settings."""

    URL: ClassVar[Any]
    ID: ClassVar[str | None] = None
    CLIENT_OPTIONS: ClassVar[dict[str, Any]] = {}
    TOOLSET_OPTIONS: ClassVar[dict[str, Any]] = {}

    @cp
    def client(self) -> Client:
        return Client(self.URL, **self.CLIENT_OPTIONS)

    def __init__(self, settings: Any = None):
        self.settings = settings
        super().__init__(
            self.client,
            id=self.ID or type(self).__name__,
            **self.TOOLSET_OPTIONS,
        )
