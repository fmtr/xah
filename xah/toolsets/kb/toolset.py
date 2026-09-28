from functools import cached_property
from typing import ClassVar

from cached_classproperty import cached_classproperty
from corio.db.search.client import Client
from corio.db.search.document import Document
from xah.toolsets.base.toolset import Base as Toolset

from xah.toolsets.kb.get import Get
from xah.toolsets.kb.list import List
from xah.toolsets.kb.query import Query


class Knowledgebase(Toolset):
    """Search and retrieve documents from the knowledgebase."""

    DOCUMENTS: ClassVar[list[type[Document]]]

    @cached_classproperty
    def TOOLS(cls):
        return [List, Query, Get]

    @cached_classproperty
    def DOCUMENTS(cls):
        return []

    @cached_property
    def client(self) -> Client:
        return Client()
