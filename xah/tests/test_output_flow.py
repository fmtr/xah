from types import SimpleNamespace

import pytest
from acp.schema import ToolCallProgress
from pydantic_ai import RunContext
from pydantic_ai.messages import ToolCallPart, ToolReturnPart
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from corio.iterator import ilist
from pydantic_acp.projection import build_tool_start_update
from pydantic_acp.serialization import DefaultOutputSerializer

from xah.class_collections import classes
from xah.server.acp.projection import build_tool_progress_update
from xah.toolsets.base.output import Output
from xah.toolsets.base.tool import Input, Tool
from xah.toolsets.base.toolset import Toolset


class ExampleOutput(Output):
    value: str

    def get_agent(self) -> str:
        return self.value


class ExampleTool(Tool, Input):
    async def run(self) -> ExampleOutput:
        return ExampleOutput(value="agent value")


class ExampleToolset(Toolset):
    @classes
    def Tools(cls):
        return [ExampleTool]


@pytest.fixture
def context():
    deps = SimpleNamespace()
    return RunContext(
        deps=deps,
        model=TestModel(),
        usage=RunUsage(),
        tool_call_id="call-1",
    )


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
    assert update.title.startswith(f"{toolset.get_name(ExampleTool)} →")
    assert list(toolset.outputs) == []
