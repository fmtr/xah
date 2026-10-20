import asyncio
import sys
from functools import cached_property
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic_acp import MemorySessionStore
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.tools import DeferredToolRequests, ToolDenied

from xah.class_collections import classes
from xah.harness.base import HarnessAcp
from xah.server.acp.server import ApprovalBridgeMetadata, SessionAgentSource
from xah.server.acp.usage import UsageReporterRegistry
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.toolset import Toolset


class Toolsets:
    def __init__(self):
        self.declined = []

    def for_tool(self, tool_name):
        return self

    async def after_decline(self, tool_name, tool_call_id, tool_args):
        self.declined.append(tool_call_id)


class DeclineTool(Tool):
    async def run(self):
        return "done"


class DeclineToolset(Toolset):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.declined = []

    @classes
    def Tools(cls):
        return [DeclineTool]

    async def after_decline(self, tool_name, tool_call_id, tool_args):
        self.declined.append((tool_name, tool_call_id, tool_args))


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
        toolsets = Toolsets()
        source = SimpleNamespace(
            get_runtime=lambda session: SimpleNamespace(
                deps=SimpleNamespace(toolsets=toolsets)
            )
        )
        return await ApprovalBridgeMetadata(source=source).resolve_deferred_approvals(
            client=Client(),
            session=SimpleNamespace(session_id="session", cwd=Path.cwd()),
            requests=requests,
            classifier=Classifier(),
        )

    resolution = asyncio.run(resolve())
    result = resolution.deferred_tool_results.approvals["call-1"]
    assert isinstance(result, ToolDenied)
    assert result.message == "The tool call was denied."


def test_sessionless_acp_agent_routes_declines_to_session_toolsets(tmp_path):
    session_store = MemorySessionStore()

    class TestXah(HarnessAcp):
        @classes
        def Toolsets(cls):
            return [DeclineToolset]

        @cached_property
        def session_store(self):
            return session_store

    with patch.object(sys, "argv", [sys.argv[0]]):
        harness = TestXah(usage_reporters=UsageReporterRegistry())
        assert harness.session is None
        agent = harness.acp_agent

    async def start_session():
        await agent.initialize(protocol_version=1)
        return await agent.new_session(cwd=str(tmp_path), mcp_servers=[])

    response = asyncio.run(start_session())
    session = session_store.get(response.session_id)

    assert response.session_id
    assert session.cwd == tmp_path.resolve()

    tool_name = DeclineToolset.tool_name(DeclineTool)
    requests = DeferredToolRequests(
        approvals=[
            ToolCallPart(
                tool_name=tool_name,
                args={},
                tool_call_id="call-1",
            )
        ],
    )

    class Client:
        async def request_permission(self, **kwargs):
            return SimpleNamespace(
                outcome=SimpleNamespace(outcome="selected", option_id="reject_once")
            )

    async def deny_tool_call():
        return await agent._config.approval_bridge.resolve_deferred_approvals(
            client=Client(),
            session=session,
            requests=requests,
            classifier=agent._tool_classifier,
        )

    resolution = asyncio.run(deny_tool_call())
    runtime = harness.agent_source.get_runtime(session)
    toolset = runtime.deps.toolsets.all.cls[DeclineToolset]
    assert isinstance(resolution.deferred_tool_results.approvals["call-1"], ToolDenied)
    assert toolset.declined == [(tool_name, "call-1", {})]


def test_acp_session_log_includes_client_info(monkeypatch):
    class Runtime:
        projections = []

        def __init__(self, **kwargs):
            pass

        def restore_session(self):
            pass

    source = SessionAgentSource(
        harness_type=Runtime,
        settings=None,
        usage_reporters=UsageReporterRegistry(),
        projection_maps=[],
    )
    source.client_info = SimpleNamespace(name="client", version="1.2.3")
    messages = []
    monkeypatch.setattr("xah.server.acp.server.logger.info", messages.append)

    source.get_runtime(SimpleNamespace(session_id="session", cwd=Path.cwd()))

    assert messages == ["ACP session started: session (client: client 1.2.3)"]
