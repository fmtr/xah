from cached_classproperty import cached_classproperty
from xah.class_collections import classes

from xah.options import base as options
from xah.toolsets.base.toolset import Toolset


class Files(Toolset):
    """Filesystem reading, writing, editing, moving, and searching tools."""

    POLICY = options.Policy.Policies.APPROVAL

    @classes
    def Tools(cls):
        from xah.toolsets.fs.edit import Edit
        from xah.toolsets.fs.mkdir import Mkdir
        from xah.toolsets.fs.move import Move
        from xah.toolsets.fs.read import Read
        from xah.toolsets.fs.read_line import ReadLine
        from xah.toolsets.fs.remove import Remove
        from xah.toolsets.fs.search import Search
        from xah.toolsets.fs.write import Write

        return [Read, ReadLine, Write, Edit, Move, Search, Mkdir, Remove]
