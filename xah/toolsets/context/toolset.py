from cached_classproperty import cached_classproperty

from xah.toolsets.base.toolset import Toolset
from xah.toolsets.context.compact import Compact


class Context(Toolset):
    """Manage the conversation context."""

    @cached_classproperty
    def TOOLS(cls):
        return [Compact]
