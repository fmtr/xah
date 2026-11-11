from typing import ClassVar

from cached_classproperty import cached_classproperty
from corio import strings
from xah.class_collections import classes

from xah.toolsets.base.toolset import Toolset
from xah.toolsets.context.compact import Compact


class Context(Toolset):
    """Manage the conversation context."""

    COMPACTION_REQUIRED_MESSAGE: ClassVar[str] = strings.trim("""
        URGENT: Context usage is {usage:.0%}. Stop the current task.
        Activate the {toolset_name} toolset. Carefully read the {tool_name} tool definition and
        follow its summary requirements exactly. Then call {tool_name}. Do not continue until
        compaction is complete.
    """)

    @classes
    def Tools(cls):
        return [Compact]
