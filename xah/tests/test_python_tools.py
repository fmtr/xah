import asyncio
from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.usage import RunUsage

from corio import Path
from corio.iterator import ilist
from xah.options.path import PathCwd
from xah.toolsets.base.tool import ValidationResult
from xah.toolsets.python.pip import Pip
from xah.toolsets.python.run import Run
from xah.toolsets.python.run_code import RunCode
from xah.toolsets.python.test import Test as PythonTest
from xah.toolsets.python.toolset import Python


def context(tmp_path):
    toolset = Python()
    cwd = Path(tmp_path)
    deps = SimpleNamespace(
        toolsets=ilist([toolset]),
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


def test_correctness_validator_runs_under_every_policy(tmp_path):
    ctx = context(tmp_path)
    tool = make(Run, ctx, args=[])
    with pytest.raises(ModelRetry, match="No arguments"):
        asyncio.run(tool.validate(ValidationResult()))


def test_run_code_has_no_length_limit(tmp_path):
    ctx = context(tmp_path)
    tool = make(RunCode, ctx, code="x" * 1001)
    result = ValidationResult()
    asyncio.run(tool.validate(result))
    assert result.messages == []
