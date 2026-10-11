from cached_classproperty import cached_classproperty
from xah.class_collections import classes

from xah.toolsets.base.toolset import Toolset
from xah.toolsets.context.compact import Compact


class Context(Toolset):
    """Manage the conversation context."""

    @classes
    def Tools(cls):
        return [Compact]
