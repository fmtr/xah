import asyncio
from types import SimpleNamespace

from pydantic_ai import RunContext
from pydantic_ai.usage import RunUsage
from corio import Path
from corio.iterator import ilist
from xah.options.path import PathCwd, PathRead, PathWrite
from xah.toolsets.fs.search import Search
from xah.toolsets.fs.toolset import Files


def context(tmp_path):
    cwd = Path(tmp_path).resolve()
    toolset = Files()
    deps = SimpleNamespace(
        toolsets=ilist([toolset]),
        options=ilist([
            PathCwd.from_cwd(cwd=cwd, description="Working directory."),
            PathRead.from_cwd(cwd=cwd, description="Read path."),
            PathWrite.from_cwd(cwd=cwd, description="Write path."),
        ]),
    )
    return RunContext(deps=deps, model=None, usage=RunUsage())


def test_file_listing_respects_glob(tmp_path):
    Path(tmp_path / "one.py").write_text("one")
    Path(tmp_path / "two.txt").write_text("two")
    ctx = context(tmp_path)
    result = asyncio.run(Search(ctx=ctx, toolset=ctx.deps.toolsets.cls[Files], glob="*.py").run())
    assert "one.py" in result
    assert "two.txt" not in result
