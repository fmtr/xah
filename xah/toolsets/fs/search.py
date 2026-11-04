import asyncio
from functools import cached_property
from typing import Annotated

from cached_classproperty import cached_classproperty
from pydantic import Field
from pydantic_ai import ModelRetry
from pydantic_acp.projection import ToolProjection as AcpToolProjection

from corio import Path, strings
from corio.function import ccp
from xah.class_collections import classes
from xah.toolsets.base.projection import Projection as ProjectionBase
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase, Tool
from xah.toolsets.fs.permissions import Permissions


class SearcherBase:
    MAX_RESULTS = 100
    SEARCH_TIMEOUT = 30

    def __init__(self, path: Path, pattern: str | None, glob: str | None, feedback):
        self.path = path
        self.pattern = pattern
        self.glob = glob
        self.feedback = feedback

    @cached_property
    def search_kwargs(self):
        search_kwargs = dict(no_ignore=True, hidden=True)
        if self.glob and self.glob != "*":
            search_kwargs |= dict(globs=[self.glob])
        return search_kwargs

    def report_result_cap(self) -> None:
        self.feedback(
            f"Search hit the {self.MAX_RESULTS}-result cap; some results were omitted. "
            "Use a more precise search."
        )

    async def run(self) -> str:
        try:
            search = asyncio.to_thread(self.search_method, **self.search_args)
            results = await asyncio.wait_for(search, timeout=self.SEARCH_TIMEOUT)
        except (TimeoutError, ValueError) as error:
            message = str(error) or "Search took too long. Narrow the search and try again."
            raise ModelRetry(message) from error

        if results:
            return self.format(results)
        return self.NO_RESULTS_MESSAGE.format(path=self.path, pattern=self.pattern)


class SearcherFiles(SearcherBase):
    NO_RESULTS_MESSAGE = "No files found in {path}"

    @cached_property
    def search_method(self):
        return self.path.search.files

    @cached_property
    def search_args(self):
        return {"max_count": self.MAX_RESULTS + 1, **self.search_kwargs}

    def format(self, entries):
        root = self.path if self.path.is_dir() else self.path.parent
        lines = []
        for entry in entries[:self.MAX_RESULTS]:
            lines.append(str(entry.relative_to(root)))
            lines.append(f"{entry.stat().st_size}b")
        if len(entries) > self.MAX_RESULTS:
            self.report_result_cap()
        return strings.join(lines, sep="\n")


class SearcherContent(SearcherBase):
    NO_RESULTS_MESSAGE = "No matches for '{pattern}'"

    @cached_property
    def search_method(self):
        return self.path.search.contents

    @cached_property
    def search_args(self):
        return {
            "patterns": [self.pattern],
            "max_total": self.MAX_RESULTS + 1,
            **self.search_kwargs,
        }

    def format(self, results):
        groups = []
        displayed = 0
        for result in results:
            remaining = self.MAX_RESULTS - displayed
            matches = result.matches[:remaining]
            lines = [str(result.path.relative_to(self.path))]
            for match in matches:
                lines.append(f"{match.line_number}:{match.line_text[:100]}")
            groups.append(strings.join(lines, sep="\n"))
            displayed += len(matches)
            if displayed >= self.MAX_RESULTS:
                self.report_result_cap()
                break
        return strings.join(groups, sep="\n-\n")


class Projection(ProjectionBase):
    def title(self) -> str:
        path = self.sig.path
        pattern = self.sig.glob or self.sig.regex
        if path and pattern:
            return f"Search {path} for {self.preview(pattern, limit=80)}"
        if pattern:
            return f"Search for {self.preview(pattern, limit=80)}"
        if path:
            return f"List {path}"
        return "Search files"

    def progress(self):
        return AcpToolProjection(
            content=[self.content(self.output_text)],
            status=self.status,
        )


class Signature(SignatureBase):
    glob: str | None = Field(default=None, description="Glob to filter search paths/filenames.")
    regex: str | None = Field(default=None, description="Regex to search **inside** files. Leave empty to search only paths/filenames.")
    path: Annotated[Path | None, Permissions(Permissions.Read)] = Field(
        default=None,
        description="Directory or file to search.",
    )


class Search(Tool, Signature):
    """Search for files or file contents."""

    KIND = Kinds.SEARCH

    @ccp
    def Projection(cls):
        return Projection

    async def run(self) -> str:
        Searcher=SearcherFiles
        if self.regex:
            Searcher=SearcherContent
        searcher = Searcher(self.path, self.regex, self.glob, self.feedback)
        return await searcher.run()
