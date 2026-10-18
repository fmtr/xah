from functools import cached_property

from cached_classproperty import cached_classproperty
from corio.db.search.client import Client
from corio.db.search.document import Document
from corio.function import cp
from corio.iterator import ilist
from xah.class_collections import classes
from xah.toolsets.base.toolset import Toolset
from xah.toolsets.kb.db import WebPage
from xah.toolsets.kb.history import ResearchHistory
from xah.toolsets.kb.get import Get
from xah.toolsets.kb.list import List
from xah.toolsets.kb.query import Query


class Knowledgebase(Toolset):
    """Search and retrieve web pages and fixed collections."""

    @classes
    def Tools(cls):
        return [Query, Get, List]

    @classes
    def Collections(cls) -> list[type[Document]]:
        return []

    @cp
    def history(self) -> ilist[ResearchHistory.Prompts]:
        return ilist()

    @cached_property
    def client(self) -> Client:
        return Client(location=Client.MEMORY)

    def collection_for(self, collection_id: str) -> type[Document]:
        if collection_id in self.Collections.name:
            return self.Collections.name[collection_id]
        return WebPage
