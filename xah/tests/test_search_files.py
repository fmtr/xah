import asyncio
from types import SimpleNamespace

import pytest
from pydantic_ai import RunContext
from pydantic_ai.usage import RunUsage
from corio import Path
from corio.iterator import ilist
from xah.options.path import PathCwd, PathRead, PathWrite
from xah.toolsets.fs.search import Search, SearcherFiles
from xah.toolsets.fs.toolset import Files


ALL_FILES = {
    "root.md",
    "docs/index.md",
    "docs/tutorials/guide.md",
    "nested/docs/decoy.md",
    "notes.txt",
}
MARKDOWN_FILES = ALL_FILES - {"notes.txt"}
DOCS_FILES = {"docs/index.md", "docs/tutorials/guide.md"}


def context(tmp_path):
    cwd = Path(tmp_path).resolve()
    toolset = Files()
    deps = SimpleNamespace(
        toolsets=ilist([toolset]),
        approval_bridge=None,
        options=ilist([
            PathCwd.from_cwd(cwd=cwd, description="Working directory."),
            PathRead.from_cwd(cwd=cwd, description="Read path."),
            PathWrite.from_cwd(cwd=cwd, description="Write path."),
        ]),
    )
    return RunContext(deps=deps, model=None, usage=RunUsage())


@pytest.fixture
def search_tree(tmp_path):
    contents = {
        "root.md": "needle root",
        "docs/index.md": "needle index",
        "docs/tutorials/guide.md": "needle guide",
        "docs/notes.txt": "needle text",
        "nested/docs/decoy.md": "needle decoy",
        "notes.txt": "needle notes",
    }
    for relative_path, content in contents.items():
        path = Path(tmp_path / relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    return Path(tmp_path)


@pytest.mark.parametrize("root_kind", ["absolute", "relative", "current"])
@pytest.mark.parametrize(
    ("glob", "expected_paths"),
    [
        pytest.param(None, ALL_FILES | {"docs/notes.txt"}, id="no-glob"),
        pytest.param("*", ALL_FILES | {"docs/notes.txt"}, id="star-glob"),
        pytest.param("*.md", MARKDOWN_FILES, id="basename-glob-recurses"),
        pytest.param("docs/*.md", {"docs/index.md"}, id="anchored-direct-children"),
        pytest.param("docs/**/*.md", DOCS_FILES, id="anchored-recursive-glob"),
    ],
)
def test_file_listing_globs_are_root_relative(
    search_tree,
    monkeypatch,
    root_kind,
    glob,
    expected_paths,
):
    if root_kind == "current":
        monkeypatch.chdir(search_tree)
        search_path = Path(".")
    elif root_kind == "relative":
        search_path = search_tree.relative_to(Path.cwd(), walk_up=True)
    else:
        search_path = search_tree.resolve()

    result = asyncio.run(
        SearcherFiles(search_path, None, glob, lambda message: None).run()
    )

    assert {str(file.path) for file in result.files} == expected_paths


def test_content_search_glob_is_root_relative(search_tree):
    ctx = context(search_tree)
    relative_root = search_tree.relative_to(Path.cwd(), walk_up=True)

    result = asyncio.run(
        Search(
            ctx=ctx,
            toolset=ctx.deps.toolsets.cls[Files],
            path=relative_root,
            regex="needle",
            glob="docs/**/*.md",
        ).run()
    )

    assert {str(group.path) for group in result.groups} == DOCS_FILES
