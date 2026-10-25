from cached_classproperty import cached_classproperty
from xah.class_collections import classes

from xah.options import base as options
from xah.toolsets.base.toolset import Toolset


class Shell(Toolset):
    """Shell execution tools."""

    POLICY = options.Policy.Policies.REQUESTABLE

    @classes
    def Tools(cls):
        from xah.toolsets.shell.run import Run

        return [Run]
