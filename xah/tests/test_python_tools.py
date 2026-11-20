import asyncio
import inspect
from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.usage import RunUsage

from corio import Path
from corio.iterator import ilist
from xah.options.path import PathCwd
from xah.toolsets.base.tool import Messages, Validation
from xah.toolsets.python.pip import Pip
from xah.toolsets.python import inspect_script
from xah.toolsets.python.inspect import Inspect
from xah.toolsets.python.run import Run
from xah.toolsets.python.run_code import RunCode
from xah.toolsets.python.test import Test as PythonTest
from xah.toolsets.python.toolset import Python


def _sample_for_inspection():
    return "indigo"


def context(tmp_path):
    toolset = Python()
    cwd = Path(tmp_path)
    deps = SimpleNamespace(
        toolsets=ilist([toolset]),
        approval_bridge=None,
        options=ilist([PathCwd.from_cwd(cwd=cwd, description="Working directory.")]),
    )
    return RunContext(deps=deps, model=None, usage=RunUsage())


def make(tool_class, ctx, **kwargs):
    return tool_class(ctx=ctx, toolset=ctx.deps.toolsets.cls[Python], **kwargs)


def test_public_name_schema_and_dsl_expression(tmp_path):
    ctx = context(tmp_path)
    tool = make(Run, ctx, args=["script.py"])
    schema = Run.model_json_schema()

    assert tool.name == "Python-Run"
    assert Run.description
    assert "ctx" not in schema["properties"]
    assert schema["properties"]["args"]["description"]
    assert tool.expression.tokens(args_only=False) == ["python", "script.py"]


def test_registered_tool_schema_excludes_context(tmp_path):
    ctx = context(tmp_path)
    toolset = ctx.deps.toolsets.cls[Python]
    tool_definition = toolset.tools[toolset.get_name(Run)].tool_def

    assert "ctx" not in tool_definition.parameters_json_schema["properties"]


def test_tool_argument_errors_hide_context_and_external_urls(tmp_path):
    ctx = context(tmp_path)
    toolset = ctx.deps.toolsets.cls[Python]
    tool_definition = toolset.tools[toolset.get_name(Run)].tool_def

    with pytest.raises(ModelRetry) as error:
        toolset.init_tool(ctx, tool_definition, {})

    message = str(error.value)
    assert "ctx" not in message
    assert "deps" not in message
    assert "https://errors.pydantic.dev" not in message
    assert "args" in message


def test_basic_python_tool_expressions(tmp_path):
    ctx = context(tmp_path)

    assert make(Pip, ctx, args=["install", "example"]).expression.tokens(args_only=False) == [
        "python",
        "-m",
        "pip",
        "install",
        "example",
    ]
    assert make(RunCode, ctx, code="print(1)").expression.tokens(args_only=False) == [
        "python",
        "-c",
        "print(1)",
    ]
    assert make(PythonTest, ctx).expression.tokens(args_only=False) == ["python", "-m", "pytest"]


def test_inspect_runs_bundled_script_with_import_path_argument(tmp_path):
    ctx = context(tmp_path)
    import_path = "sample_package.module with space"
    tool = make(Inspect, ctx, import_path=import_path)
    schema = Inspect.model_json_schema()

    toolset = ctx.deps.toolsets.cls[Python]
    assert toolset.get_name(Inspect) in toolset.tools
    assert Inspect.SCRIPT == Path(inspect_script.__file__).read_text()
    assert "import_path" in schema["properties"]
    assert "code" not in schema["properties"]
    assert tool.expression.tokens(args_only=False) == [
        "python",
        "-c",
        Inspect.SCRIPT,
        import_path,
    ]


def test_inspection_script_shows_plain_function_details_without_source():
    import_path = f"{__name__}._sample_for_inspection"
    source_lines, first_line = inspect.getsourcelines(_sample_for_inspection)
    last_line = first_line + len(source_lines) - 1

    rendered = inspect_script.Inspection(import_path).text

    assert f"Import: {import_path}" in rendered
    assert "Type: function" in rendered
    assert f"Lines: {first_line}-{last_line}" in rendered
    assert 'return "indigo"' not in rendered
    assert "`" not in rendered


def test_inspection_script_lists_module_members_as_plain_text():
    source_lines, _ = inspect.getsourcelines(inspect_script)
    rendered = inspect_script.Inspection(inspect_script.__name__).text
    members = next(line for line in rendered.splitlines() if line.startswith("Members: "))

    assert "Type: module" in rendered
    assert f"Lines: 1-{len(source_lines)}" in rendered
    assert "Inspection" in members.removeprefix("Members: ").split(", ")
    assert "- " not in members
    assert "```" not in rendered
    assert "##" not in rendered
    assert "class Inspection:" not in rendered


def test_inspection_script_marks_unavailable_details():
    rendered = inspect_script.Inspection("builtins.len").text

    assert "Path: [unavailable]" in rendered
    assert "Lines: [unavailable]" in rendered
    assert "Signature: [unavailable]" in rendered
    assert "Members: [unavailable]" in rendered
    assert rendered.endswith(inspect.getdoc(len))
    assert rendered.index("Members:") < rendered.index("Documentation:")


def test_inspection_script_reports_unresolvable_import():
    with pytest.raises(SystemExit):
        inspect_script.Inspection("missing_sample_package.unavailable").text


def test_python_run_rejects_missing_arguments(tmp_path):
    ctx = context(tmp_path)
    tool = make(Run, ctx, args=[])
    tool.validation = Validation()
    asyncio.run(tool.validate())

    assert tool.validation.abort
    assert len(tool.validation.messages.errors) == 1


def test_run_code_has_no_length_limit(tmp_path):
    ctx = context(tmp_path)
    tool = make(RunCode, ctx, code="x" * 1001)
    tool.validation = Validation()
    asyncio.run(tool.validate())
    assert tool.validation.messages == Messages()
