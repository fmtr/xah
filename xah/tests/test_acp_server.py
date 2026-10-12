import asyncio
from functools import cached_property
from pathlib import Path
from types import SimpleNamespace

from pydantic_acp import (
    DefaultPermissionToolCallBuilder,
    MemorySessionStore,
    PermissionRequestContext,
    compose_projection_maps,
)
from pydantic_acp.projection import FileEditToolCallContent
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import DeferredToolRequests, ToolDenied

from xah.server.acp.server import ApprovalBridgeMetadata
from xah.harness.base import HarnessAcp
from xah.server.acp.usage import UsageReporterRegistry


class Classifier:
    def classify(self, tool_name, raw_input):
        return "edit"

    def approval_policy_key(self, tool_name, raw_input):
        return (tool_name, tuple(sorted(raw_input)))

def test_denied_permission_returns_validation_diagnostics_to_model():
    class Client:
        async def request_permission(self, **kwargs):
            return SimpleNamespace(
                outcome=SimpleNamespace(outcome="selected", option_id="reject_once")
            )

    requests = DeferredToolRequests(
        approvals=[
            ToolCallPart(
                tool_name="write_file",
                args={"path": "broken.py", "content": "def broken("},
                tool_call_id="call-1",
            )
        ],
    )

    async def resolve():
        return await ApprovalBridgeMetadata().resolve_deferred_approvals(
            client=Client(),
            session=SimpleNamespace(session_id="session", cwd=Path.cwd()),
            requests=requests,
            classifier=Classifier(),
        )

    resolution = asyncio.run(resolve())
    result = resolution.deferred_tool_results.approvals["call-1"]
    assert isinstance(result, ToolDenied)
    assert result.message == "The tool call was denied."


def test_acp_session_starts_without_a_model(tmp_path):
    session_store = MemorySessionStore()
    class TestXah(HarnessAcp):
        @cached_property
        def session_store(self):
            return session_store

    agent = TestXah(usage_reporters=UsageReporterRegistry()).acp_agent
    assert not agent._config.projection_maps

    async def start_session():
        await agent.initialize(protocol_version=1)
        return await agent.new_session(cwd=str(tmp_path), mcp_servers=[])

    response = asyncio.run(start_session())
    session = session_store.get(response.session_id)

    assert response.session_id
    assert session.cwd == tmp_path.resolve()
    assert session.session_model_id is None
    assert agent._tool_classifier.classify("Files-Write") == "edit"

    raw_input = {"path": "example.py", "content": "print('ok')\n"}
    update = DefaultPermissionToolCallBuilder().build_tool_call_update(
        PermissionRequestContext(
            session=session,
            tool_call=ToolCallPart(
                tool_name="Files-Write",
                args=raw_input,
                tool_call_id="call-1",
            ),
            raw_input=raw_input,
            cwd=tmp_path,
            classifier=agent._tool_classifier,
            projection_map=compose_projection_maps(agent._config.projection_maps),
        )
    )
    assert update.kind == "edit"
    assert update.content[0] == (
        FileEditToolCallContent(
            type="diff",
            path="example.py",
            old_text="",
            new_text="print('ok')\n",
        )
    )
