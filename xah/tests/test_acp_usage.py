import asyncio
import sys
from functools import cached_property
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import patch

from acp.schema import TextContentBlock, ToolCallProgress, UsageUpdate
from fastmcp import FastMCP
from corio.iterator import ilist
from pydantic_acp import AdapterModel
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from xah.class_collections import classes
from xah.harness.base import HarnessAcp
from xah.toolsets.base.mcp import ToolsetMCP
from xah.server.acp.usage import UsageReporterRegistry


class RecordingClient:
    def __init__(self):
        self.updates = []

    async def session_update(self, **kwargs):
        self.updates.append(kwargs)


def test_acp_session_emits_context_usage_update(tmp_path):
    class TestAdapterModel(AdapterModel):
        CONTEXT_COMPACTION_THRESHOLD: ClassVar[float] = 0.8

    class TestHarnessAcp(HarnessAcp):
        @cached_property
        def models(self):
            return ilist([
                TestAdapterModel(
                    model_id="test",
                    name="test",
                    override=TestModel(custom_output_text="fixed response"),
                )
            ])

        @cached_property
        def agent(self):
            agent = Agent(
                model=TestModel(custom_output_text="fixed response"),
                deps_type=self.deps_type,
                capabilities=self.agent_capabilities,
            )
            agent.instructions("Answer briefly.")
            return agent

    harness = TestHarnessAcp(
        session=SimpleNamespace(cwd=tmp_path, session_id="test-session"),
        usage_reporters=UsageReporterRegistry(),
    )
    with patch.object(sys, "argv", [sys.argv[0]]):
        agent = harness.acp_agent
    client = RecordingClient()
    agent.on_connect(client)

    async def run_prompt():
        await agent.initialize(protocol_version=1)
        session = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        return await agent.prompt(
            session.session_id,
            [TextContentBlock(type="text", text="hello")],
        )

    response = asyncio.run(run_prompt())

    assert response.stop_reason == "end_turn"
    usage_updates = [
        item["update"]
        for item in client.updates
        if isinstance(item["update"], UsageUpdate)
    ]
    assert len(usage_updates) == 1
    assert usage_updates[0].used > 0
    assert usage_updates[0].size > usage_updates[0].used


def test_acp_prompt_runs_native_mcp_tool_and_records_progress(tmp_path):
    server = FastMCP("synthetic-session-service")
    calls = []

    @server.tool
    def sample_signal() -> str:
        calls.append("invoked")
        return "synthetic-payload"

    class SampleMCP(ToolsetMCP):
        URL = server

    class TestAdapterModel(AdapterModel):
        CONTEXT_COMPACTION_THRESHOLD: ClassVar[float] = 0.8

    class TestHarnessAcp(HarnessAcp):
        @classes
        def Instructions(cls):
            return []

        @classes
        def MCPs(cls):
            return [SampleMCP]

        @cached_property
        def models(self):
            return ilist([
                TestAdapterModel(
                    model_id="synthetic",
                    name="Synthetic",
                    override=TestModel(),
                )
            ])

    harness = TestHarnessAcp(
        session=SimpleNamespace(cwd=tmp_path, session_id="synthetic-session"),
        usage_reporters=UsageReporterRegistry(),
    )
    with patch.object(sys, "argv", [sys.argv[0]]):
        agent = harness.acp_agent
    client = RecordingClient()
    agent.on_connect(client)

    async def run_prompt():
        await agent.initialize(protocol_version=1)
        session = await agent.new_session(cwd=str(tmp_path), mcp_servers=[])
        return await agent.prompt(
            session.session_id,
            [TextContentBlock(type="text", text="Inspect a synthetic signal.")],
        )

    response = asyncio.run(run_prompt())
    progress = [
        item["update"]
        for item in client.updates
        if isinstance(item["update"], ToolCallProgress)
    ]

    assert response.stop_reason == "end_turn"
    assert calls == ["invoked"]
    mcp_progress = [
        update for update in progress if "synthetic-payload" in (update.raw_output or "")
    ]

    assert len(mcp_progress) == 1
    assert mcp_progress[0].status == "completed"
