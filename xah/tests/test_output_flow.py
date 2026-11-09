from types import SimpleNamespace

import pytest
from acp.schema import ToolCallProgress
from pydantic_ai import RunContext
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from corio import Path
from corio.iterator import ilist
from pydantic_acp.projection import build_tool_start_update
from pydantic_acp.serialization import DefaultOutputSerializer

from xah.class_collections import classes
from xah.server.acp.projection import build_tool_progress_update
from xah.toolsets.base.input import Input
from xah.toolsets.base.output import Output
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.toolset import Toolset
from xah.options.path import PathCwd, PathRead, PathWrite
from xah.toolsets.fs.toolset import Files
from xah.toolsets.fs.write import Write


class ExampleOutput(Output):
    value: str

    @property
    def agent(self) -> str:
        return self.value


class ExampleTool(Tool, Input):
    async def run(self) -> ExampleOutput:
        return ExampleOutput(value="agent value")


class ExampleToolset(Toolset):
    @classes
    def Tools(cls):
        return [ExampleTool]


class BrokenProjectionInput(Input):
    @property
    def projection(self):
        raise RuntimeError("projection failed")


class BrokenProjectionTool(Tool, BrokenProjectionInput):
    async def run(self):
        return "unused"


class BrokenProjectionOutput(Output):
    value: str

    @property
    def projection(self):
        raise RuntimeError("output projection failed")


class BrokenProjectionToolset(Toolset):
    @classes
    def Tools(cls):
        return [BrokenProjectionTool]


@pytest.fixture
def context():
    deps = SimpleNamespace()
    return RunContext(
        deps=deps,
        model=TestModel(),
        usage=RunUsage(),
        tool_call_id="call-1",
    )


def test_projection_errors_return_traceback_projection():
    tool_name = BrokenProjectionToolset.get_name(BrokenProjectionTool)
    raw_args = {}

    projection = BrokenProjectionToolset.project_start(tool_name, raw_input=raw_args)

    assert projection.title == f"{tool_name} [PROJECTION ERROR]"
    traceback_content = projection.content[0].content.text
    assert f"tool_name: {tool_name}" in traceback_content
    assert f"raw_args: {raw_args!r}" in traceback_content
    assert traceback_content.startswith(f"tool_name: {tool_name}\n")
    assert "RuntimeError: projection failed" in traceback_content


@pytest.mark.asyncio
async def test_bare_toolset_returns_agent_value_without_retaining_output(context):
    toolset = ExampleToolset()
    tool = (await toolset.get_tools(context))[toolset.get_name(ExampleTool)]

    result = await toolset.call_tool(toolset.get_name(ExampleTool), {}, context, tool)

    assert result == "agent value"
    assert toolset.outputs is None
    assert "call_id" not in ExampleOutput.model_json_schema()["properties"]
    assert "call_id" not in ExampleOutput(value="x").model_dump()


@pytest.mark.asyncio
async def test_acp_progress_handles_denied_call_without_registered_output(context):
    toolset = ExampleToolset()
    toolset.outputs = ilist()
    toolsets = SimpleNamespace(for_tool=lambda name: toolset)
    classifier = SimpleNamespace(classify=lambda name, raw_input=None: "other")
    start = build_tool_start_update(
        ToolCallPart(
            tool_name=toolset.get_name(ExampleTool),
            args={},
            tool_call_id="call-1",
        ),
        classifier=classifier,
        cwd=None,
        projection_map=toolset,
    )
    update = build_tool_progress_update(
        ToolReturnPart(
            tool_name=toolset.get_name(ExampleTool),
            content="The tool call was denied.",
            tool_call_id="call-1",
            outcome="denied",
        ),
        classifier=classifier,
        cwd=None,
        known_start=start,
        projection_map=toolset,
        serializer=DefaultOutputSerializer(),
        toolsets=toolsets,
    )

    assert isinstance(update, ToolCallProgress)
    assert update.status == "failed"
    assert list(toolset.outputs) == []


@pytest.mark.asyncio
async def test_progress_projection_errors_preserve_tool_status():
    tool_name = BrokenProjectionToolset.get_name(BrokenProjectionTool)
    output = BrokenProjectionOutput(value="result")

    projection = BrokenProjectionToolset.project_progress(
        tool_name,
        raw_input={},
        raw_output=output,
        serialized_output='{"value":"result"}',
        status="completed",
    )

    assert projection.title == f"{tool_name} [PROJECTION ERROR]"
    assert projection.status == "completed"
    error_content = projection.content[0].content.text
    assert f"tool_name: {tool_name}" in error_content
    assert "raw_args: {}" in error_content
    assert "RuntimeError: output projection failed" in error_content


def test_invalid_input_projection_is_not_replaced_by_progress_validation():
    tool_name = Files.get_name(Write)
    raw_args = {"path": "broken.py"}

    start = Files.project_start(tool_name, raw_input=raw_args)
    progress = Files.project_progress(
        tool_name,
        raw_input=raw_args,
        raw_output=ExampleOutput(value="unused"),
        serialized_output='{"value":"unused"}',
        status="failed",
    )

    assert start.title == f"{tool_name} [INVALID CALL]"
    assert progress is None

    toolset = Files()
    toolset.outputs = ilist()
    classifier = SimpleNamespace(classify=lambda name, raw_input=None: "edit")
    start_update = build_tool_start_update(
        ToolCallPart(tool_name=tool_name, args=raw_args, tool_call_id="invalid-call"),
        classifier=classifier,
        cwd=None,
        projection_map=toolset,
    )
    progress_update = build_tool_progress_update(
        ToolReturnPart(
            tool_name=tool_name,
            content="Input validation failed.",
            tool_call_id="invalid-call",
            outcome="success",
        ),
        classifier=classifier,
        cwd=None,
        known_start=start_update,
        projection_map=toolset,
        serializer=DefaultOutputSerializer(),
        toolsets=SimpleNamespace(for_tool=lambda name: toolset),
    )

    assert progress_update.title == start_update.title
    assert progress_update.content == start_update.content


@pytest.mark.asyncio
async def test_acp_write_start_and_progress_preserve_supplied_content(tmp_path):
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
    ctx = RunContext(
        deps=deps,
        model=TestModel(),
        usage=RunUsage(),
        tool_call_id="call-write",
    )
    toolset.outputs = ilist()
    tool_name = Files.get_name(Write)
    raw_args = {"path": "item.txt", "text": "alpha"}
    classifier = SimpleNamespace(classify=lambda name, raw_input=None: "edit")
    start = build_tool_start_update(
        ToolCallPart(
            tool_name=tool_name,
            args=raw_args,
            tool_call_id=ctx.tool_call_id,
        ),
        classifier=classifier,
        cwd=cwd,
        projection_map=toolset,
    )
    assert start.content[0].new_text == "alpha"

    tools = await toolset.wrapper.get_tools(ctx)
    result = await toolset.wrapper.call_tool(
        tool_name,
        raw_args,
        ctx,
        tools[tool_name],
    )
    assert (cwd / "item.txt").read_text() == "alpha"

    toolsets = SimpleNamespace(for_tool=lambda name: toolset)
    progress = build_tool_progress_update(
        ToolReturnPart(
            tool_name=tool_name,
            content=result,
            tool_call_id=ctx.tool_call_id,
            outcome="success",
        ),
        classifier=classifier,
        cwd=cwd,
        known_start=start,
        projection_map=toolset,
        serializer=DefaultOutputSerializer(),
        toolsets=toolsets,
    )
    assert progress.title.startswith("Writing 1 line to `item.txt`")
    assert progress.status == "completed"


@pytest.mark.asyncio
async def test_acp_progress_uses_original_output_and_cleans_registry(context):
    toolset = ExampleToolset()
    toolset.outputs = ilist()
    tool = (await toolset.get_tools(context))[toolset.get_name(ExampleTool)]
    result = await toolset.call_tool(toolset.get_name(ExampleTool), {}, context, tool)
    part = ToolReturnPart(
        tool_name=toolset.get_name(ExampleTool),
        content=result,
        tool_call_id="call-1",
        outcome="success",
    )
    toolsets = SimpleNamespace(for_tool=lambda name: toolset)
    classifier = SimpleNamespace(classify=lambda name, raw_input=None: "other")
    start = build_tool_start_update(
        ToolCallPart(
            tool_name=toolset.get_name(ExampleTool),
            args={},
            tool_call_id="call-1",
        ),
        classifier=classifier,
        cwd=None,
        projection_map=toolset,
    )

    update = build_tool_progress_update(
        part,
        classifier=classifier,
        cwd=None,
        known_start=start,
        projection_map=toolset,
        serializer=DefaultOutputSerializer(),
        toolsets=toolsets,
    )

    assert isinstance(update, ToolCallProgress)
    assert update.status == "completed"
    assert update.title.startswith(f"{toolset.get_name(ExampleTool)}(`{{}}`) →")
    assert list(toolset.outputs) == []
