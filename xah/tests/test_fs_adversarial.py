import asyncio
import csv
import io
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.usage import RunUsage

from corio import Path, jsn, strings, toml
from corio.iterator import ilist
from xah.options.path import PathCwd, PathRead, PathWrite
from xah.toolsets.fs.edit import Edit
from xah.toolsets.fs.mkdir import Mkdir
from xah.toolsets.fs.move import Move
from xah.toolsets.fs.read import Read
from xah.toolsets.fs.read_line import ReadLine
from xah.toolsets.fs.remove import Remove
from xah.toolsets.fs.search import Search
from xah.toolsets.fs.toolset import Files
from xah.toolsets.fs.write import Write


EVENT_RECORDS = [
    {"event": "stock.received", "request_id": "REQ-3101", "units": 18},
    {"event": "stock.reserved", "request_id": "REQ-3102", "units": 3},
    {"event": "stock.audit", "request_id": "REQ-3103", "units": 0},
    {"event": "stock.reconciled", "request_id": "REQ-3104", "units": 15},
]
EVENT_LINES = [
    json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    for record in EVENT_RECORDS
]


@pytest.fixture
def filesystem_tree(tmp_path):
    root = Path(tmp_path / "workspace")
    outside = Path(tmp_path / "outside" / "private")
    stock_csv = io.StringIO()
    csv.writer(stock_csv, lineterminator="\n").writerows(
        [
            ("depot_id", "sku", "available_units", "last_counted"),
            ("AMS-03", "SKU-44018", 8, "2025-02-14T09:30:00Z"),
            ("OSL-01", "SKU-77102", 34, "2025-02-14T09:35:00Z"),
            ("LIS-07", "SKU-44018", 0, "2025-02-14T09:41:00Z"),
        ]
    )
    security_fields = {
        "Contact": "mailto:security@example.test",
        "Expires": "2026-12-31T23:59:00Z",
    }
    security_text = "\n".join(
        f"{name}: {value}" for name, value in security_fields.items()
    )
    files = {
        "README.md": strings.trim("""
            # Northstar Service

            A small inventory service for regional depots.

            ## Operations

            Run `python -m northstar.api` from the repository root.
        """),
        "src/northstar/api.py": strings.trim('''
            """HTTP entry point for the depot inventory service."""
            from northstar.inventory import Inventory

            SERVICE_NAME = "northstar-inventory"
            RELEASE_CODE = "REL-2048"

            def healthcheck() -> dict[str, str]:
                return {"service": SERVICE_NAME, "status": "ready"}
        '''),
        "src/northstar/inventory.py": strings.trim('''
            """Read depot stock records and report below-threshold items."""
            from dataclasses import dataclass

            @dataclass
            class StockRecord:
                depot_id: str
                sku: str
                available_units: int

                def needs_restock(self, threshold: int = 12) -> bool:
                    return self.available_units < threshold
        '''),
        "config/service.toml": toml.to_toml(
            {
                "service": {
                    "name": "northstar-inventory",
                    "region": "eu-west",
                    "request_timeout_seconds": 4.5,
                },
                "logging": {"level": "INFO", "format": "json"},
            }
        ),
        "config/routes.json": jsn.to_json(
            {
                "health": "/healthz",
                "inventory": "/v2/depots/{depot_id}/stock",
                "request_id_header": "X-Request-ID",
            }
        ),
        "data/depot-stock.csv": stock_csv.getvalue(),
        "data/events.ndjson": "\n".join(EVENT_LINES) + "\n",
        "docs/operations/runbook.md": strings.trim("""
            # Depot inventory operations

            Incident reference: INCIDENT-7314
            The north depot accepts inventory updates during the daily window.
            Escalate a repeated 503 response to the platform on-call engineer.
            Use the exact request identifier when correlating audit records.
        """),
        "docs/archive/2024-review.md": strings.trim("""
            # 2024 service review

            The north depot migration completed without data loss.
            Follow-up ticket: OPS-982.
        """),
        "reports/Q1 stock review.md": strings.trim("""
            # Q1 stock review

            SKU-44018 was below the replenishment threshold at two depots.
        """),
        "docs/日本語/手順.md": strings.trim("""
            # 在庫サービス

            監査記録を確認してください。
        """),
        ".well-known/security.txt": security_text,
        "data/empty.csv": "",
    }
    for relative_path, content in files.items():
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    outside.mkdir(parents=True)
    (outside / "credentials.json").write_text(
        jsn.to_json(
            {
                "service_token": "outside-workspace-sentinel",
                "rotation": "quarterly",
            }
        ),
        encoding="utf-8",
    )
    return root


def context(root, *, read_root=".", write_root="."):
    cwd = Path(root).resolve()
    toolset = Files()
    deps = SimpleNamespace(
        toolsets=ilist([toolset]),
        approval_bridge=None,
        settings=SimpleNamespace(path=SimpleNamespace(secrets=["**/.env"])),
        options=ilist(
            [
                PathCwd.from_cwd(cwd=cwd, description="Working directory."),
                PathRead.from_cwd(
                    cwd=cwd,
                    value=read_root,
                    description="Read path.",
                ),
                PathWrite.from_cwd(
                    cwd=cwd,
                    value=write_root,
                    description="Write path.",
                ),
            ]
        ),
    )
    return RunContext(deps=deps, model=None, usage=RunUsage())


def make(tool_class, ctx, **kwargs):
    return tool_class(ctx=ctx, toolset=ctx.deps.toolsets.cls[Files], **kwargs)


FILE_TOOLS = [
    pytest.param(Read, "path", {}, id="read"),
    pytest.param(ReadLine, "path", {"line_number": 1}, id="read-line"),
    pytest.param(Write, "path", {"text": "attacker-controlled write"}, id="write"),
    pytest.param(Edit, "path", {"old_text": "service", "new_text": "changed"}, id="edit"),
    pytest.param(Move, "source", {"target": "reports/moved.json", "is_copy": True}, id="copy"),
    pytest.param(Search, "path", {"regex": "service"}, id="search"),
    pytest.param(Mkdir, "path", {}, id="mkdir"),
    pytest.param(Remove, "path", {}, id="remove"),
]


@pytest.mark.parametrize(
    ("tool_class", "path_field", "extra_fields"),
    FILE_TOOLS,
)
@pytest.mark.parametrize(
    "attacker_path",
    [
        "../outside/private/credentials.json",
        "../../outside/private/credentials.json",
        "src/../../outside/private/credentials.json",
        "/etc/passwd",
    ],
)
def test_every_file_tool_rejects_paths_outside_both_permissions(
    filesystem_tree,
    tool_class,
    path_field,
    extra_fields,
    attacker_path,
):
    ctx = context(filesystem_tree)
    kwargs = {path_field: attacker_path, **extra_fields}

    with pytest.raises(ValidationError, match="permission"):
        make(tool_class, ctx, **kwargs)


@pytest.mark.parametrize(
    ("tool_class", "path_field", "extra_fields"),
    FILE_TOOLS,
)
def test_every_file_tool_rejects_a_symlink_that_resolves_outside_the_workspace(
    filesystem_tree,
    tool_class,
    path_field,
    extra_fields,
):
    external_directory = filesystem_tree.parent / "outside" / "private"
    link = filesystem_tree / "docs" / "external-private"
    link.symlink_to(external_directory, target_is_directory=True)
    ctx = context(filesystem_tree)
    kwargs = {
        path_field: "docs/external-private/credentials.json",
        **extra_fields,
    }

    with pytest.raises(ValidationError, match="permission"):
        make(tool_class, ctx, **kwargs)


@pytest.mark.parametrize(
    ("tool_class", "path_field", "extra_fields"),
    [
        pytest.param(Write, "path", {"text": "stolen"}, id="write-target"),
        pytest.param(Edit, "path", {"old_text": "service", "new_text": "changed"}, id="edit-target"),
        pytest.param(Mkdir, "path", {}, id="mkdir-target"),
        pytest.param(Remove, "path", {}, id="remove-target"),
        pytest.param(Move, "target", {"source": "docs/operations/runbook.md"}, id="move-target"),
    ],
)
def test_mutating_tool_destinations_cannot_escape_write_permission(
    filesystem_tree,
    tool_class,
    path_field,
    extra_fields,
):
    kwargs = {
        path_field: "../outside/private/credentials.json",
        **extra_fields,
    }

    with pytest.raises(ValidationError, match="PathWrite permission"):
        make(tool_class, context(filesystem_tree), **kwargs)


@pytest.mark.parametrize(
    ("read_root", "write_root", "path", "tool_class", "extra_fields", "expected_allowed"),
    [
        pytest.param("docs", ".", "docs/operations/runbook.md", Read, {}, True, id="read-inside-read-root"),
        pytest.param("docs", ".", "docs/operations/runbook.md", Search, {"regex": "INCIDENT"}, True, id="search-inside-read-root"),
        pytest.param("reports", ".", "README.md", Read, {}, False, id="read-outside-narrow-read-root"),
        pytest.param(".", "docs", "README.md", Write, {"text": "no"}, False, id="write-outside-narrow-write-root"),
        pytest.param(".", "docs", "README.md", Edit, {"old_text": "Northstar", "new_text": "Other"}, False, id="edit-outside-narrow-write-root"),
        pytest.param(".", "reports", "docs/operations/runbook.md", Remove, {}, False, id="remove-outside-narrow-write-root"),
        pytest.param(".", "reports", "docs/operations/runbook.md", Move, {"target": "reports/runbook.md"}, False, id="move-source-outside-narrow-write-root"),
    ],
)
def test_each_operation_enforces_its_read_or_write_root(
    filesystem_tree,
    read_root,
    write_root,
    path,
    tool_class,
    extra_fields,
    expected_allowed,
):
    ctx = context(filesystem_tree, read_root=read_root, write_root=write_root)
    path_field = "source" if tool_class is Move else "path"
    kwargs = {path_field: path, **extra_fields}

    if expected_allowed:
        make(tool_class, ctx, **kwargs)
        return

    with pytest.raises(ValidationError, match="permission"):
        make(tool_class, ctx, **kwargs)


@pytest.mark.parametrize(
    ("offset", "limit", "expected"),
    [
        pytest.param(
            0,
            2,
            strings.trim(f"""
                1:{EVENT_LINES[0]}
                2:{EVENT_LINES[1]}
            """),
            id="head",
        ),
        pytest.param(2, 1, f"3:{EVENT_LINES[2]}", id="middle"),
        pytest.param(
            -2,
            2,
            strings.trim(f"""
                3:{EVENT_LINES[2]}
                4:{EVENT_LINES[3]}
            """),
            id="tail",
        ),
        pytest.param(-50, 1, f"1:{EVENT_LINES[0]}", id="negative-offset-before-file"),
    ],
)
def test_read_line_windows_match_real_ndjson_records(
    filesystem_tree,
    offset,
    limit,
    expected,
):
    ctx = context(filesystem_tree)
    tool = make(Read, ctx, path="data/events.ndjson", offset=offset, limit=limit)

    assert asyncio.run(tool.run()).agent == expected


def test_reading_an_empty_file_at_offset_zero_returns_an_empty_result(filesystem_tree):
    tool = make(Read, context(filesystem_tree), path="data/empty.csv")

    assert asyncio.run(tool.run()).agent == ""


def test_reading_an_empty_file_rejects_a_positive_offset(filesystem_tree):
    tool = make(Read, context(filesystem_tree), path="data/empty.csv", offset=1)

    with pytest.raises(ModelRetry, match="Offset 1 exceeds the file length of 0 lines"):
        asyncio.run(tool.run())


@pytest.mark.parametrize(
    ("line_number", "offset", "limit", "expected"),
    [
        pytest.param(2, 0, 12, "request_id=R", id="line-prefix"),
        pytest.param(2, 11, 10, "REQ-7314-α", id="unicode-offset"),
        pytest.param(2, 100_000, 12, "", id="offset-past-line-end"),
        pytest.param(3, 19_986, 10, "ZZZZZZZZZZ", id="tail-of-long-line"),
    ],
)
def test_read_line_returns_requested_character_ranges(
    filesystem_tree,
    line_number,
    offset,
    limit,
    expected,
):
    long_line = "trace=" + "Z" * 19_990 + "END"
    source = filesystem_tree / "data" / "long-traces.log"
    long_context = "request_id=REQ-7314-α; context=depot; " + "x" * 10_000
    source_text = strings.trim(f"""
        short header
        {long_context}
        {long_line}
    """)
    source.write_text(source_text, encoding="utf-8")
    tool = make(
        ReadLine,
        context(filesystem_tree),
        path="data/long-traces.log",
        line_number=line_number,
        offset=offset,
        limit=limit,
    )

    assert asyncio.run(tool.run()).text == expected


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        pytest.param({"path": "data/events.ndjson", "line_number": 0}, "line_number", id="zero-line"),
        pytest.param({"path": "data/events.ndjson", "line_number": -1}, "line_number", id="negative-line"),
        pytest.param({"path": "data/events.ndjson", "line_number": 1, "offset": -1}, "offset", id="negative-char-offset"),
        pytest.param({"path": "data/events.ndjson", "line_number": 1, "limit": 0}, "limit", id="zero-char-limit"),
        pytest.param({"path": "data/events.ndjson", "line_number": 1, "limit": 20_001}, "limit", id="char-limit-over-cap"),
    ],
)
def test_read_line_rejects_invalid_numeric_bounds(filesystem_tree, kwargs, field):
    with pytest.raises(ValidationError, match=field):
        make(ReadLine, context(filesystem_tree), **kwargs)


@pytest.mark.parametrize(
    ("text", "relative_path"),
    [
        pytest.param("", "reports/empty export.txt", id="empty-content"),
        pytest.param("東京; Montréal; Reykjavík\n", "reports/locale roster.csv", id="unicode-and-spaces"),
        pytest.param("first\r\nsecond\r\n", "reports/windows-export.csv", id="crlf"),
        pytest.param("header\x00payload\n", "reports/binary-marker.log", id="embedded-nul-content"),
    ],
)
def test_write_preserves_unusual_but_valid_file_contents(filesystem_tree, text, relative_path):
    tool = make(Write, context(filesystem_tree), path=relative_path, text=text)

    asyncio.run(tool.run())

    assert (filesystem_tree / relative_path).read_bytes() == text.encode("utf-8")


@pytest.mark.parametrize(
    ("old_text", "new_text", "replace_all", "initial_text", "expected", "occurrence_count"),
    [
        pytest.param("north", "south", False, "The north depot; north depot.\n", "The south depot; north depot.\n", 1, id="first-literal-occurrence"),
        pytest.param("north", "south", True, "The north depot; north depot.\n", "The south depot; south depot.\n", 2, id="all-occurrences"),
        pytest.param("a+b", "a*b", False, "Regex-like token a+b is literal.\n", "Regex-like token a*b is literal.\n", 1, id="regex-metacharacters-are-literal"),
        pytest.param("東京", "大阪", False, "配送先は東京です。\n", "配送先は大阪です。\n", 1, id="unicode-edit"),
    ],
)
def test_edit_uses_exact_literal_replacements(
    filesystem_tree,
    old_text,
    new_text,
    replace_all,
    initial_text,
    expected,
    occurrence_count,
):
    target = filesystem_tree / "reports" / "edit-cases.txt"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(initial_text, encoding="utf-8")
    tool = make(
        Edit,
        context(filesystem_tree),
        path="reports/edit-cases.txt",
        old_text=old_text,
        new_text=new_text,
        replace_all=replace_all,
    )

    result = asyncio.run(tool.run())

    assert target.read_text(encoding="utf-8") == expected
    assert result.occurrence_count == occurrence_count


@pytest.mark.parametrize(
    "relative_path",
    [
        "reports/2025/Q2/approved",
        "docs/日本語/新しい手順",
        "reports/space in name/child directory",
    ],
)
def test_mkdir_builds_nested_unicode_and_spaced_paths(filesystem_tree, relative_path):
    result = asyncio.run(make(Mkdir, context(filesystem_tree), path=relative_path).run())

    assert (filesystem_tree / relative_path).is_dir()
    assert result.path == (filesystem_tree / relative_path).resolve()


@pytest.mark.parametrize(
    ("source", "target", "is_copy", "source_remains"),
    [
        pytest.param("docs/operations/runbook.md", "reports/runbook-copy.md", True, True, id="copy-file"),
        pytest.param("docs/operations/runbook.md", "reports/runbook-moved.md", False, False, id="move-file"),
        pytest.param("src/northstar", "reports/northstar-snapshot", True, True, id="copy-nested-directory"),
        pytest.param("src/northstar", "reports/northstar-archive", False, False, id="move-nested-directory"),
    ],
)
def test_move_and_copy_preserve_content_and_expected_source_state(
    filesystem_tree,
    source,
    target,
    is_copy,
    source_remains,
):
    source_path = filesystem_tree / source
    source_files = {
        child.relative_to(source_path): child.read_bytes()
        for child in source_path.rglob("*")
        if child.is_file()
    } if source_path.is_dir() else {Path("."): source_path.read_bytes()}
    tool = make(
        Move,
        context(filesystem_tree),
        source=source,
        target=target,
        is_copy=is_copy,
    )

    result = asyncio.run(tool.run())

    target_path = filesystem_tree / target
    assert target_path.exists()
    assert source_path.exists() is source_remains
    if target_path.is_dir():
        assert {
            child.relative_to(target_path): child.read_bytes()
            for child in target_path.rglob("*")
            if child.is_file()
        } == source_files
    else:
        assert target_path.read_bytes() == source_files[Path(".")]
    assert result.is_copy is is_copy


@pytest.mark.parametrize(
    ("relative_path", "expected_type"),
    [
        pytest.param("reports/Q1 stock review.md", "File", id="remove-spaced-file"),
        pytest.param("docs/archive", "Directory", id="remove-nested-tree"),
    ],
)
def test_remove_deletes_only_the_selected_workspace_entry(filesystem_tree, relative_path, expected_type):
    result = asyncio.run(make(Remove, context(filesystem_tree), path=relative_path).run())

    assert result.item_type == expected_type
    assert not (filesystem_tree / relative_path).exists()


@pytest.mark.parametrize(
    ("regex", "glob", "expected_relative_paths"),
    [
        pytest.param(None, "docs/**/*.md", {"docs/operations/runbook.md", "docs/archive/2024-review.md", "docs/日本語/手順.md"}, id="nested-doc-markdown"),
        pytest.param(r"INCIDENT-\d+", None, {"docs/operations/runbook.md"}, id="regex-content-match"),
        pytest.param("north depot", "docs/**/*.md", {"docs/operations/runbook.md", "docs/archive/2024-review.md"}, id="regex-and-glob-cross-product"),
    ],
)
def test_search_returns_expected_workspace_relative_results(
    filesystem_tree,
    regex,
    glob,
    expected_relative_paths,
):
    result = asyncio.run(
        make(
            Search,
            context(filesystem_tree),
            path=".",
            regex=regex,
            glob=glob,
        ).run()
    )

    if regex:
        assert {str(group.path) for group in result.groups} == expected_relative_paths
    else:
        assert {str(file.path) for file in result.files} == expected_relative_paths


@pytest.mark.parametrize("glob", ["../outside/**", "../../**/credentials.json", "/etc/**"])
def test_file_listing_globs_cannot_escape_the_selected_root(filesystem_tree, glob):
    result = asyncio.run(
        make(Search, context(filesystem_tree), path=".", glob=glob).run()
    )

    assert result.files == []


def test_search_rejects_an_empty_regex(filesystem_tree):
    with pytest.raises(ValidationError, match="regex"):
        make(Search, context(filesystem_tree), path=".", regex="")


def test_search_accepts_nonempty_regex_that_can_match_empty_text(filesystem_tree):
    tool = make(Search, context(filesystem_tree), path=".", regex=".?")

    assert tool.regex == ".?"


@pytest.mark.parametrize("regex", ["[", "(", r"(?P<duplicate>x)(?P<duplicate>y)"])
def test_invalid_regular_expressions_are_reported_as_model_retries(filesystem_tree, regex):
    tool = make(Search, context(filesystem_tree), path=".", regex=regex)

    with pytest.raises(ModelRetry):
        asyncio.run(tool.run())


@pytest.mark.parametrize(
    ("tool_class", "kwargs"),
    [
        pytest.param(Write, {"path": None, "text": "x"}, id="null-path"),
        pytest.param(Write, {"path": 42, "text": "x"}, id="integer-path"),
        pytest.param(Write, {"path": ["reports", "x.txt"], "text": "x"}, id="list-path"),
        pytest.param(Write, {"path": {"name": "x"}, "text": "x"}, id="mapping-path"),
        pytest.param(Mkdir, {"path": None}, id="null-directory-path"),
        pytest.param(Mkdir, {"path": 3.14}, id="float-directory-path"),
        pytest.param(Mkdir, {"path": ["reports"]}, id="list-directory-path"),
    ],
)
def test_filesystem_tools_reject_non_path_input_shapes(filesystem_tree, tool_class, kwargs):
    with pytest.raises(ValidationError):
        make(tool_class, context(filesystem_tree), **kwargs)
