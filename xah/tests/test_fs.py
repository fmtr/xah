import asyncio
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.usage import RunUsage

from corio import Path
from corio.iterator import ilist
from xah.options.path import PathCwd, PathRead, PathWrite
from xah.toolsets.base.tool import Messages, Validation, ValidationAbort
from xah.toolsets.fs.edit import Edit, EditWarnings, ValidEdit
from xah.toolsets.fs.metadata import FileType, Metadata
from xah.toolsets.fs.move import Move
from xah.toolsets.fs.write import FileWriteOutput
from xah.toolsets.fs.read import Read
from xah.toolsets.fs.search import Search
from xah.toolsets.fs.permissions import Permissions
from xah.toolsets.fs.toolset import Files
from xah.toolsets.fs.write import Write


def context(tmp_path):
    cwd = Path(tmp_path).resolve()
    toolset = Files()
    deps = SimpleNamespace(
        toolsets=ilist([toolset]),
        approval_bridge=None,
        settings=SimpleNamespace(path=SimpleNamespace(secrets=["**/.env"])),
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
    assert metadata.permission is Permissions.Write


def test_search_defaults_to_the_current_working_directory(tmp_path):
    ctx = context(tmp_path)
    tool = make(Search, ctx)

    assert tool.path == Path(tmp_path)


def test_ctx_is_validated_but_absent_from_schema_and_dump(tmp_path):
    ctx = context(tmp_path)
    tool = make(Write, ctx, path="note.txt", text="hello")

    schema = Write.model_json_schema()
    assert "ctx" not in schema["properties"]
    assert "validation" not in schema["properties"]
    assert "text" in schema["properties"]
    assert "content" not in schema["properties"]
    assert "ctx" not in tool.model_dump()
    assert "validation" not in tool.model_dump()
    assert schema["properties"]["path"]["type"] == "string"


def test_write_validate_and_run(tmp_path):
    ctx = context(tmp_path)
    tool = make(Write, ctx, path="nested/note.txt", text="hello\n")

    tool.validation = Validation()
    asyncio.run(tool.validate())
    assert tool.validation.messages == Messages()
    asyncio.run(tool.run())

    assert Path(tmp_path / "nested/note.txt").read_text() == "hello\n"


def test_validation_abort_records_message_and_skips_remaining_validators(
    tmp_path,
    monkeypatch,
):
    message = "VALIDATION-ABORT-6C"

    async def abort(self):
        raise ValidationAbort(message)

    later_validator_calls = []

    async def later(self):
        later_validator_calls.append(self)

    monkeypatch.setattr(ValidEdit, "validate", abort)
    monkeypatch.setattr(EditWarnings, "validate", later)
    tool = make(Edit, context(tmp_path), path="note.txt", old_text="a", new_text="b")

    asyncio.run(tool.validate())

    assert tool.validation.abort
    assert tool.validation.messages.errors == [message]
    assert later_validator_calls == []


def test_empty_validation_abort_stops_validation_without_adding_an_error(
    tmp_path,
    monkeypatch,
):
    async def abort(self):
        raise ValidationAbort()

    monkeypatch.setattr(ValidEdit, "validate", abort)
    tool = make(Edit, context(tmp_path), path="note.txt", old_text="a", new_text="b")

    asyncio.run(tool.validate())

    assert tool.validation.abort
    assert tool.validation.messages.errors == []


def test_permission_failure_occurs_during_model_validation(tmp_path):
    ctx = context(tmp_path)
    outside_path = tmp_path.parent / f"{tmp_path.name}-escape.txt"

    with pytest.raises(ValidationError):
        make(Write, ctx, path=f"../{tmp_path.name}-escape.txt", text="no")

    assert not outside_path.exists()


def test_env_file_requires_approval(tmp_path):
    Path(tmp_path / ".env").write_text("KEY=value\n")
    ctx = context(tmp_path)
    tool = make(Read, ctx, path=".env")
    tool.validation = Validation()

    asyncio.run(tool.validate())

    assert tool.validation.approval
    approval_messages = tool.validation.messages.approval

    assert len(approval_messages) == 1
    assert str(Path(tmp_path / ".env").resolve()) in approval_messages[0]


def test_metadata_reads_file_and_directory_details(tmp_path):
    ctx = context(tmp_path)
    file_path = Path(tmp_path / "note.txt")
    file_path.write_text("hello")
    directory_path = Path(tmp_path / "folder")
    directory_path.mkdir()

    file_tool = make(Metadata, ctx, path="note.txt")
    file_metadata = asyncio.run(file_tool.run())
    directory_metadata = asyncio.run(make(Metadata, ctx, path="folder").run())

    assert file_metadata.file_type is FileType.FILE
    assert file_metadata.size_bytes == 5
    assert file_metadata.owner
    assert file_metadata.owner_id == file_path.stat().st_uid
    assert file_metadata.group
    assert file_metadata.group_id == file_path.stat().st_gid
    assert len(file_metadata.permissions) == 9
    assert file_metadata.modified_at.tzinfo is not None
    assert directory_metadata.file_type is FileType.DIRECTORY
    assert directory_metadata.size_bytes == directory_path.stat().st_size


@pytest.mark.parametrize(
    ("tool_class", "path_field", "extra_fields"),
    [
        pytest.param(Metadata, "path", {}, id="metadata"),
        pytest.param(Search, "path", {}, id="search"),
        pytest.param(Move, "source", {"target": "next.dat"}, id="move-source"),
    ],
)
def test_read_permission_rejects_missing_paths(
    tmp_path,
    tool_class,
    path_field,
    extra_fields,
):
    ctx = context(tmp_path)
    kwargs = {path_field: "absent.dat", **extra_fields}

    with pytest.raises(ValidationError) as error:
        make(tool_class, ctx, **kwargs)

    missing_path = str(Path(tmp_path / "absent.dat").resolve())
    message = Files.validation_error_message(error.value)

    assert missing_path in message
    assert not message.startswith(":")


def test_metadata_requires_read_permission(tmp_path):
    ctx = context(tmp_path)

    with pytest.raises(ValidationError):
        make(Metadata, ctx, path="../outside.txt")


def test_toolset_publishes_class_model_schemas(tmp_path):
    ctx = context(tmp_path)
    toolset = ctx.deps.toolsets.cls[Files]
    tools = asyncio.run(toolset.get_tools(ctx))
    schema = Write.model_json_schema()
    write_name = toolset.get_name(Write)

    assert set(tools) == {toolset.get_name(tool) for tool in type(toolset).Tools}
    assert tools[write_name].tool_def.parameters_json_schema == schema
    assert schema["properties"]["path"]["type"] == "string"


def test_read_rejects_offset_beyond_file_length(tmp_path):
    path = Path(tmp_path / "short.txt")
    path.write_text("one\ntwo\n")
    ctx = context(tmp_path)
    tool = make(Read, ctx, path="short.txt", offset=2)

    with pytest.raises(ModelRetry):
        asyncio.run(tool.run())


def test_read_preserves_whitespace_without_truncation_feedback(tmp_path, monkeypatch):
    path = Path(tmp_path / "normal.txt")
    path.write_text("    indented\n\t tabbed\ntrailing spaces  \n")
    ctx = context(tmp_path)
    tool = make(Read, ctx, path="normal.txt")
    feedback = []
    monkeypatch.setattr(Read, "feedback", lambda self, message: feedback.append(message))

    result = asyncio.run(tool.run())

    assert result.agent == "1:    indented\n2:\t tabbed\n3:trailing spaces  "
    assert feedback == []


def test_read_truncates_an_extremely_long_line_and_provides_feedback(tmp_path, monkeypatch):
    path = Path(tmp_path / "massive.txt")
    path.write_text("x" * (1024 * 1024))
    ctx = context(tmp_path)
    tool = make(Read, ctx, path="massive.txt")
    feedback = []
    monkeypatch.setattr(Read, "feedback", lambda self, message: feedback.append(message))

    result = asyncio.run(tool.run())

    line = result.lines[0]

    assert line.number == 1
    assert Read.MAX_LINE_LENGTH - 10 < len(line.text) <= Read.MAX_LINE_LENGTH
    assert line.text.startswith("x" * 100)
    assert line.text.endswith("x" * 100)
    assert "…" in line.text
    assert len(feedback) == 1


def test_read_stops_after_many_long_lines_and_provides_feedback(tmp_path, monkeypatch):
    line_count = 100
    path = Path(tmp_path / "long-lines.txt")
    path.write_text("\n".join("x" * 20_000 for _ in range(line_count)))
    ctx = context(tmp_path)
    tool = make(Read, ctx, path="long-lines.txt")
    feedback = []
    monkeypatch.setattr(Read, "feedback", lambda self, message: feedback.append(message))

    result = asyncio.run(tool.run())

    assert [line.number for line in result.lines] == [1, 2]
    assert [line.text for line in result.lines] == ["x" * 20_000] * 2
    assert len(result.agent.encode()) <= Read.MAX_OUTPUT_LENGTH
    assert len(feedback) == 1
