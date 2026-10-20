import asyncio
from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.usage import RunUsage

from corio import Path
from corio.iterator import ilist
from xah.options.path import PathCwd, PathRead, PathWrite
from xah.toolsets.base.tool import Validation
from xah.toolsets.fs.edit import Edit
from xah.toolsets.fs.mkdir import Mkdir
from xah.toolsets.fs.move import Move
from xah.toolsets.fs.read import Read
from xah.toolsets.fs.remove import Remove
from xah.toolsets.fs.search import Search
from xah.toolsets.fs.permissions import Permissions
from xah.toolsets.fs.toolset import Files
from xah.toolsets.fs.write import Write


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


def make(tool_class, ctx, **kwargs):
    return tool_class(ctx=ctx, toolset=ctx.deps.toolsets.cls[Files], **kwargs)


def test_path_metadata_drives_resolution_and_permissions(tmp_path):
    ctx = context(tmp_path)
    tool = make(Edit, ctx, path="note.txt", old_text="a", new_text="b")
    metadata = next(metadata for metadata in type(tool).model_fields["path"].metadata if isinstance(metadata, Permissions))

    assert tool.path == Path(tmp_path / "note.txt").resolve()
    assert metadata == {Permissions.Read, Permissions.Write}


def test_ctx_is_validated_but_absent_from_schema_and_dump(tmp_path):
    ctx = context(tmp_path)
    tool = make(Write, ctx, path="note.txt", content="hello")

    assert "ctx" not in Write.model_json_schema()["properties"]
    assert "validation" not in Write.model_json_schema()["properties"]
    assert "ctx" not in tool.model_dump()
    assert "validation" not in tool.model_dump()
    assert Write.model_json_schema()["properties"]["path"]["type"] == "string"


def test_write_validate_and_run(tmp_path):
    ctx = context(tmp_path)
    tool = make(Write, ctx, path="nested/note.txt", content="hello\n")

    tool.validation = Validation()
    asyncio.run(tool.validate())
    assert tool.validation.messages == []
    assert asyncio.run(tool.run()).startswith("Wrote")
    assert Path(tmp_path / "nested/note.txt").read_text() == "hello\n"


def test_permission_failure_occurs_during_validation(tmp_path):
    ctx = context(tmp_path)
    tool = make(Write, ctx, path="../escape.txt", content="no")

    with pytest.raises(ModelRetry, match="Permission Denied"):
        tool.validation = Validation()
        asyncio.run(tool.validate())


def test_env_file_requires_approval_and_reports_secret_access(tmp_path):
    ctx = context(tmp_path)
    tool = make(Read, ctx, path=".env")
    tool.validation = Validation()

    asyncio.run(tool.validate())

    assert tool.validation.approval
    assert tool.validation.messages == [f'Accessing secrets file: "{tmp_path / ".env"}"']


def test_read_edit_move_search_and_remove(tmp_path):
    ctx = context(tmp_path)
    source = Path(tmp_path / "source.txt")
    source.write_text("one\nneedle\n")

    assert "needle" in asyncio.run(make(Read, ctx, path="source.txt").run())
    edit = make(Edit, ctx, path="source.txt", old_text="needle", new_text="changed")
    edit.validation = Validation()
    asyncio.run(edit.validate())
    assert edit.validation.messages == []
    asyncio.run(edit.run())
    assert "changed" in source.read_text()
    assert "source.txt" in asyncio.run(make(Search, ctx, pattern="changed").run())
    asyncio.run(make(Move, ctx, source="source.txt", target="target.txt", is_copy=True).run())
    assert Path(tmp_path / "target.txt").exists()
    asyncio.run(make(Remove, ctx, path="target.txt").run())
    assert not Path(tmp_path / "target.txt").exists()
    asyncio.run(make(Mkdir, ctx, path="directory").run())
    assert Path(tmp_path / "directory").is_dir()


def test_toolset_publishes_class_model_schemas(tmp_path):
    ctx = context(tmp_path)
    toolset = ctx.deps.toolsets.cls[Files]
    tools = asyncio.run(toolset.get_tools(ctx))
    schema = Write.model_json_schema()
    write_name = toolset.tool_name(Write)

    assert set(tools) == {toolset.tool_name(tool) for tool in type(toolset).Tools}
    assert tools[write_name].tool_def.description == Write.description
    assert tools[write_name].tool_def.parameters_json_schema == schema
    assert schema["properties"]["path"]["type"] == "string"


def test_read_warns_via_feedback_when_offset_exceeds_file_length(tmp_path, monkeypatch):
    path = Path(tmp_path / "short.txt")
    path.write_text("one\ntwo\n")
    ctx = context(tmp_path)
    tool = make(Read, ctx, path="short.txt", offset=2)
    feedback = []
    monkeypatch.setattr(Read, "feedback", lambda self, message: feedback.append(message))

    result = asyncio.run(tool.run())

    assert result == ""
    assert feedback == [
        "Offset 2 exceeds the file length of 2 lines; no lines were shown."
    ]


def test_read_preserves_whitespace_without_truncation_feedback(tmp_path, monkeypatch):
    path = Path(tmp_path / "normal.txt")
    path.write_text("    indented\n\t tabbed\ntrailing spaces  \n")
    ctx = context(tmp_path)
    tool = make(Read, ctx, path="normal.txt")
    feedback = []
    monkeypatch.setattr(Read, "feedback", lambda self, message: feedback.append(message))

    result = asyncio.run(tool.run())

    assert result == "1:    indented\n2:\t tabbed\n3:trailing spaces  "
    assert feedback == []


def test_read_truncates_an_extremely_long_line_and_provides_feedback(tmp_path, monkeypatch):
    path = Path(tmp_path / "massive.txt")
    path.write_text("x" * (1024 * 1024))
    ctx = context(tmp_path)
    tool = make(Read, ctx, path="massive.txt")
    feedback = []
    monkeypatch.setattr(Read, "feedback", lambda self, message: feedback.append(message))

    result = asyncio.run(tool.run())

    assert result.startswith("1:")
    assert len(result) < 21_000
    assert feedback == [
        "1 line (1) exceeded the per-line display limit; truncation was applied."
    ]


def test_read_stops_after_many_long_lines_and_provides_feedback(tmp_path, monkeypatch):
    line_count = 100
    path = Path(tmp_path / "long-lines.txt")
    path.write_text("\n".join("x" * 20_000 for _ in range(line_count)))
    ctx = context(tmp_path)
    tool = make(Read, ctx, path="long-lines.txt")
    feedback = []
    monkeypatch.setattr(Read, "feedback", lambda self, message: feedback.append(message))

    result = asyncio.run(tool.run())

    assert result.startswith("001:")
    assert len(result.encode()) <= 50_000
    assert feedback == [
        "Not all lines were shown because the file contains extremely long lines; 98 lines were omitted."
    ]
