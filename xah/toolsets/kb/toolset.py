from functools import cached_property
from typing import ClassVar

from cached_classproperty import cached_classproperty
from corio.db.search.client import Client
from corio.db.search.document import Document
from xah.toolsets.kb.db import WebPage
from xah.toolsets.base.toolset import Toolset as Toolset

from xah.toolsets.kb.get import Get
from xah.toolsets.kb.query import Query


class Knowledgebase(Toolset):
    """Search and retrieve documents from the knowledgebase."""

    DOCUMENT: ClassVar[type[Document]] = WebPage

    @cached_classproperty
    def TOOLS(cls):
        return [Query, Get]

    @cached_property
    def client(self) -> Client:
        return Client()
