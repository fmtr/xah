import asyncio
from functools import cached_property
from typing import Annotated

from cached_classproperty import cached_classproperty
from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from pydantic_ai import ModelRetry

from corio import Path, dm, strings
from corio.function import ccp
from xah.class_collections import classes
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.output import Output
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.fs.permissions import Permissions


class SearchFile(dm.Base):
    path: Path
    size: int


class SearchMatch(dm.Base):
    line_number: int
    line_text: str


class SearchMatchGroup(dm.Base):
    path: Path
    matches: list[SearchMatch]


class SearchOutput(Output):
    @property
    def agent(self) -> str:
        raise NotImplementedError

    @property
    def content(self):
        return [self.content_block(self.agent)]


class SearchFilesOutput(SearchOutput):
    path: Path
    root: Path
    files: list[SearchFile]

    @property
    def agent(self) -> str:
        if not self.files:
            return f"No files found in {self.path}"

        lines = []
        for file in self.files:
            lines.extend((str(file.path), f"{file.size}b"))
        return strings.join(lines, sep="\n")


class SearchContentOutput(SearchOutput):
    root: Path
    pattern: str
    groups: list[SearchMatchGroup]

    @property
    def agent(self) -> str:
        if not self.groups:
            return f"No matches for '{self.pattern}'"

        groups = []
        for group in self.groups:
            lines = [str(group.path)]
            lines.extend(
                f"{match.line_number}:{match.line_text[:100]}"
                for match in group.matches
            )
            groups.append(strings.join(lines, sep="\n"))
        return strings.join(groups, sep="\n-\n")

    @property
    def locations(self):
        locations = []
        for group in self.groups:
            path = self.root / group.path
            for match in group.matches:
                locations.append(self.tool_location(path, line=match.line_number - 1))
        return locations


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

    async def run(self) -> SearchOutput:
        try:
            search = asyncio.to_thread(self.search_method, **self.search_args)
            results = await asyncio.wait_for(search, timeout=self.SEARCH_TIMEOUT)
        except (TimeoutError, ValueError) as error:
            message = str(error) or "Search took too long. Narrow the search and try again."
            raise ModelRetry(message) from error

        return self.output(results)

    @property
    def search_method(self):
        raise NotImplementedError

    @property
    def search_args(self):
        raise NotImplementedError

    def output(self, results) -> SearchOutput:
        raise NotImplementedError


class SearcherFiles(SearcherBase):
    @cached_property
    def search_method(self):
        return self.path.search.files

    @cached_property
    def search_args(self):
        return {"max_count": self.MAX_RESULTS + 1, **self.search_kwargs}

    def output(self, entries) -> SearchFilesOutput:
        root = self.path if self.path.is_dir() else self.path.parent
        files = [
            SearchFile(path=entry.relative_to(root), size=entry.stat().st_size)
            for entry in entries[:self.MAX_RESULTS]
        ]
        if len(entries) > self.MAX_RESULTS:
            self.report_result_cap()
        return SearchFilesOutput(path=self.path, root=root, files=files)


class SearcherContent(SearcherBase):
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

    def output(self, results) -> SearchContentOutput:
        groups = []
        displayed = 0
        for result in results:
            remaining = self.MAX_RESULTS - displayed
            if remaining == 0:
                self.report_result_cap()
                break

            matches = result.matches[:remaining]
            groups.append(
                SearchMatchGroup(
                    path=result.path.relative_to(self.path),
                    matches=[
                        SearchMatch(
                            line_number=match.line_number,
                            line_text=match.line_text,
                        )
                        for match in matches
                    ],
                )
            )
            displayed += len(matches)
            if len(result.matches) > remaining:
                self.report_result_cap()
                break

        return SearchContentOutput(
            root=self.path,
            pattern=self.pattern,
            groups=groups,
        )


class Input(InputBase):
    glob: str | None = Field(default=None, description="Glob to filter search paths/filenames.")
    regex: str | None = Field(default=None, description="Regex to search **inside** files. Leave empty to search only paths.")
    path: Annotated[Path | None, Permissions(Permissions.Read)] = Field(
        default=None,
        description="Directory or file to search.",
    )

    @property
    def title(self):
        pattern = self.glob or self.regex
        if self.path and pattern:
            path = f"`{self.path}`"
            search_pattern = f"`{self.preview(pattern, limit=20)}`"
            return f"Searching {path} for {search_pattern}"
        if pattern:
            return f"Searching for `{self.preview(pattern, limit=20)}`"
        if self.path:
            return f"Listing `{self.path}`"
        return "Searching files"

    @property
    def projection(self):
        locations = [self.tool_location(self.path)] if self.path else None
        return AcpToolProjection(title=self.title, locations=locations)


class Search(Tool, Input):
    """Search for files or file contents."""

    KIND = Kinds.SEARCH

    async def run(self) -> SearchOutput:
        searcher_class = SearcherContent if self.regex else SearcherFiles
        searcher = searcher_class(self.path, self.regex, self.glob, self.feedback)
        return await searcher.run()
