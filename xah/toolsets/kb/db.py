from contextlib import asynccontextmanager
from typing import Annotated, ClassVar

from corio.db.search.builder import Builder
from corio.db.search.document import Document, Index, Point
from corio.hash import get_hash_int
from corio.function import ccp


class WebPage(Document):
    """A fetched web page stored as searchable Markdown."""

    collection_id: Annotated[str, Index()]
    title: Annotated[str, Index()]
    url: Annotated[str, Index()]
    APPROVAL: ClassVar[bool] = False
    IS_MULTI = False

    @ccp
    def Point(cls) -> type[Point]:
        point = type(
            f"{cls.__name__}{Point.__name__}",
            (Point,),
            {"__module__": cls.__module__, "Document": cls},
        )
        return point

    @ccp
    def Builder(cls) -> type[Builder]:
        return WebPageBuilder


class WebPageBuilder(Builder):
    """Build a WebPage collection from runtime documents."""

    Document = WebPage

    @asynccontextmanager
    async def disable_hnsw(self):
        yield

    def get_point(self, data: WebPage) -> Point:
        point = self.Document.Point(
            id=get_hash_int(data.id),
            vector=[],
        )
        point.document = data
        return point
