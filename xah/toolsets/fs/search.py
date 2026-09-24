import asyncio
from functools import cached_property
from typing import Annotated, ClassVar

from cached_classproperty import cached_classproperty
from pydantic import Field
from pydantic_ai import ModelRetry

from corio import Path, strings
from xah.constants import PROJECTION_SEARCH_TOOL_NAMES
from xah.toolsets.fs.permissions import FileTool, Permissions, PermissionsValidator


class SearcherBase:
    MAX_RESULTS = 100
    SEARCH_TIMEOUT = 120

    def __init__(self, path: Path, pattern: str | None, glob: str | None):
        self.path = path
        self.pattern = pattern
        self.glob = glob

    @cached_property
    def search_kwargs(self):
        if not self.glob or self.glob == "*":
            return {}
        return {"globs": [self.glob]}

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
            lines.append("# ... more files omitted")
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
                break
        return strings.join(groups, sep="\n-\n")


class Search(FileTool):
    """Search for files or file contents."""

    pattern: str | None = Field(default=None, description="Content pattern. Omit to list files.")
    path: Annotated[Path, Permissions(Permissions.Read)] = Field(
        default_factory=lambda: Path("."),
        description="Directory or file to search.",
    )
    glob: str | None = Field(default=None, description="Optional file glob filter.")

    projections: ClassVar = PROJECTION_SEARCH_TOOL_NAMES

    @cached_classproperty
    def VALIDATORS(cls):
        return [SearchPermissions]

    async def run(self) -> str:
        searcher_type = SearcherFiles if self.pattern is None else SearcherContent
        searcher = searcher_type(self.path, self.pattern, self.glob)
        return await searcher.run()


class SearchPermissions(PermissionsValidator, Search):
    pass
