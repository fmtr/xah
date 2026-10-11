from functools import cached_property

from cached_classproperty import cached_classproperty
from xah.class_collections import classes
from corio.db.search.client import Client
from xah.toolsets.base.toolset import Toolset
from xah.toolsets.kb.get import Get
from xah.toolsets.kb.query import Query


class Knowledgebase(Toolset):
    """Search and retrieve web pages from the in-memory knowledgebase."""

    @classes
    def Tools(cls):
        return [Query, Get]

    @cached_property
    def client(self) -> Client:
        #return Client(location=Client.MEMORY)
        return Client()
