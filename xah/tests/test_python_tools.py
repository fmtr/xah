import asyncio
from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.usage import RunUsage

from corio import Path
from corio.iterator import ilist
from xah.toolsets.python.pip import Pip
from xah.toolsets.python.run import Run
from xah.toolsets.python.run_code import RunCode
from xah.toolsets.python.test import Test as PythonTest
from xah.toolsets.python.toolset import Python


def context(tmp_path):
    toolset = Python()
    deps = SimpleNamespace(cwd=Path(tmp_path), toolsets=ilist([toolset]))
    return RunContext(deps=deps, model=None, usage=RunUsage())


def test_public_name_schema_and_dsl_expression(tmp_path):
    tool = Run(ctx=context(tmp_path), args=["script.py"])
    schema = Run.model_json_schema()

    assert Run.name == "Python-Run"
    assert Run.description
    assert "ctx" not in schema["properties"]
    assert schema["properties"]["args"]["description"]
    assert tool.expression.tokens(args_only=False) == ["python", "script.py"]


def test_basic_python_tool_expressions(tmp_path):
    ctx = context(tmp_path)

    assert Pip(ctx=ctx, args=["install", "example"]).expression.tokens(args_only=False) == [
        "python",
        "-m",
        "pip",
        "install",
        "example",
    ]
    assert RunCode(ctx=ctx, code="print(1)").expression.tokens(args_only=False) == [
        "python",
        "-c",
        "print(1)",
    ]
    assert PythonTest(ctx=ctx).expression.tokens(args_only=False) == ["python", "-m", "pytest"]


def test_correctness_validator_runs_under_every_policy(tmp_path):
    tool = Run(ctx=context(tmp_path), args=[])
    with pytest.raises(ModelRetry, match="No arguments"):
        asyncio.run(tool.validate())


def test_run_code_has_no_length_limit(tmp_path):
    tool = RunCode(ctx=context(tmp_path), code="x" * 1001)
    assert asyncio.run(tool.validate()) == []
