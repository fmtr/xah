from functools import cached_property
from typing import Never

from corio.logs import logger
from pydantic_ai import ToolFailed
from tavily import AsyncTavilyClient

from xah.toolsets.base.tool import Tool


class WebTool(Tool):
    @cached_property
    def client(self) -> AsyncTavilyClient:
        return self.toolset.client

    def fail(self, error: Exception) -> Never:
        tool_name = self.toolset.tool_name(type(self))
        logger.warning(f"{tool_name} failed: {error}")
        message = f"The web request failed: {error}. The web service may be temporarily unavailable."
        raise ToolFailed(message) from error
