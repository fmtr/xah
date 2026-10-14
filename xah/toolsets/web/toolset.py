from functools import cached_property

from cached_classproperty import cached_classproperty
from xah.class_collections import classes
from tavily import AsyncTavilyClient

from xah.toolsets.base.toolset import Toolset
from xah.toolsets.web.fetch import Fetch
from xah.toolsets.web.research import Research
from xah.toolsets.web.request import Request
from xah.toolsets.web.search import Search


class Web(Toolset):
    """Search and research the web."""

    @cached_property
    def client(self) -> AsyncTavilyClient:
        return AsyncTavilyClient()

    @classes
    def Tools(cls):
        return [Fetch, Research, Request]
