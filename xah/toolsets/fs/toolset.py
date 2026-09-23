from xah.options import base as options
from xah.toolsets.base.toolset import Base
from xah.toolsets.fs.edit import Edit
from xah.toolsets.fs.mkdir import Mkdir
from xah.toolsets.fs.move import Move
from xah.toolsets.fs.read import Read
from xah.toolsets.fs.remove import Remove
from xah.toolsets.fs.search import Search
from xah.toolsets.fs.write import Write


class Files(Base):
    """Filesystem reading, writing, editing, moving, and searching tools."""
    POLICY = options.APPROVAL
    TOOLS = (Read, Write, Edit, Move, Search, Mkdir, Remove)
