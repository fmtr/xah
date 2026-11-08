import asyncio
from functools import cached_property
from typing import Annotated

from cached_classproperty import cached_classproperty
from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from pydantic_ai import ModelRetry

from corio import Path, strings
from corio.function import ccp
from xah.class_collections import classes
from xah.toolsets.base.output import OutputString
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool
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


class SearchOutput(OutputString):
    @property
    def locations(self):
        request = self.request
        input_model = request.input
        if not input_model.regex:
            return super().locations

        base = Path(request.cwd or ".")
        if input_model.path:
            base = Path(input_model.path)
            if not base.is_absolute() and request.cwd is not None:
                base = Path(request.cwd) / base

        locations = []
        for group in self.output.split("\n-\n"):
            lines = group.splitlines()
            result_path = Path(lines[0])
            if not result_path.is_absolute():
                result_path = base / result_path
            for match in lines[1:]:
                line_number, separator, _ = match.partition(":")
                if not separator or not line_number.isdigit():
                    continue
                location = self.tool_location(result_path, line=int(line_number) - 1)
                locations.append(location)

        return locations or super().locations

    @property
    def projection(self):
        request = self.request
        return AcpToolProjection(
            content=[self.content_block(self.output)],
            locations=self.locations,
            title=self.title,
            status=request.status,
        )


class Input(InputBase):
    glob: str | None = Field(default=None, description="Glob to filter search paths/filenames.")
    regex: str | None = Field(default=None, description="Regex to search **inside** files. Leave empty to search only paths/filenames.")
    path: Annotated[Path | None, Permissions(Permissions.Read)] = Field(
        default=None,
        description="Directory or file to search.",
    )

    @property
    def title(self):
        pattern = self.glob or self.regex
        if self.path and pattern:
            path = f"`{self.path}`"
            search_pattern = f"`{self.preview(pattern, limit=80)}`"
            return f"Searching {path} for {search_pattern}"
        if pattern:
            return f"Searching for `{self.preview(pattern, limit=80)}`"
        if self.path:
            return f"Listing `{self.path}`"
        return "Searching files"

    @property
    def projection(self):
        locations = [self.tool_location(self.path)] if self.path else None
        return AcpToolProjection(title=self.title, locations=locations)

    glob: str | None = Field(default=None, description="Glob to filter search paths/filenames.")
    regex: str | None = Field(default=None, description="Regex to search **inside** files. Leave empty to search only paths/filenames.")
    path: Annotated[Path | None, Permissions(Permissions.Read)] = Field(
        default=None,
        description="Directory or file to search.",
    )


class Search(Tool, Input):
    """Search for files or file contents."""

    KIND = Kinds.SEARCH

    async def run(self) -> SearchOutput:
        Searcher=SearcherFiles
        if self.regex:
            Searcher=SearcherContent
        searcher = Searcher(self.path, self.regex, self.glob, self.feedback)
        return SearchOutput(output=await searcher.run())
