import asyncio
import sys
from functools import cached_property
from types import SimpleNamespace
from unittest.mock import patch

from acp.schema import TextContentBlock, UsageUpdate
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from xah.harness.base import Harness
from xah.server.acp.usage import UsageReporterRegistry


class RecordingClient:
    def __init__(self):
        self.updates = []

    async def session_update(self, **kwargs):
        self.updates.append(kwargs)


def test_acp_session_emits_context_usage_update(tmp_path):
    class TestHarness(Harness):
        @cached_property
        def agent(self):
            agent = Agent(
                model=TestModel(custom_output_text="fixed response"),
                deps_type=self.deps_type,
                capabilities=self.agent_capabilities,
            )
            agent.instructions("Answer briefly.")
            return agent

    harness = TestHarness(
        session=SimpleNamespace(cwd=tmp_path, session_id="test-session"),
        usage_reporters=UsageReporterRegistry(),
    )
    with patch.object(sys, "argv", [sys.argv[0]]):
        assert any(
            type(capability).__name__ == "ContextManagerCapability"
            for capability in harness.agent_capabilities
        )
        configured_agent = harness.agent
        assert any(
            type(capability).__name__ == "ContextManagerCapability"
            for capability in configured_agent._root_capability.capabilities
        )
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
