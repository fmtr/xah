import asyncio
from types import SimpleNamespace

from pydantic_acp import AdapterConfig, BlackBoxHarness, MemorySessionStore
from pydantic_ai import Agent, ModelResponse
from pydantic_ai.messages import ModelRequest, TextPart, ToolCallPart, ToolReturnPart, UserPromptPart
from pydantic_ai.models.function import FunctionModel

from xah.server.acp.thinking import AgentAcp
from xah.server.acp.usage import UsageReporterRegistry


def test_cancelled_prompt_keeps_completed_tool_exchange_for_follow_up(tmp_path):
    async def exercise():
        hold_started = asyncio.Event()
        changes = []
        follow_up_messages = []
        baseline_prompt = "Keep the baseline marker."
        action_prompt = "Perform the synthetic operation."
        follow_up_prompt = "What happened before the stop?"

        async def respond(messages, _info):
            latest_prompt = next(
                (
                    part.content
                    for message in reversed(messages)
                    if isinstance(message, ModelRequest)
                    for part in reversed(message.parts)
                    if isinstance(part, UserPromptPart)
                ),
                None,
            )
            if latest_prompt == baseline_prompt:
                return ModelResponse(parts=[TextPart("baseline retained")])
            if latest_prompt == follow_up_prompt:
                follow_up_messages.append(messages.copy())
                return ModelResponse(parts=[TextPart("follow-up received")])

            action_returned = any(
                isinstance(part, ToolReturnPart) and part.tool_name == "record_observation"
                for message in messages
                for part in message.parts
            )
            if action_returned:
                return ModelResponse(
                    parts=[ToolCallPart("wait_for_stop", {}, tool_call_id="wait-call")]
                )

            return ModelResponse(
                parts=[ToolCallPart("record_observation", {}, tool_call_id="action-call")]
            )

        agent = Agent(FunctionModel(respond), output_type=str)

        @agent.tool_plain
        async def record_observation() -> str:
            changes.append("applied")
            return "operation completed"

        @agent.tool_plain
        async def wait_for_stop() -> str:
            hold_started.set()
            await asyncio.Event().wait()
            return "unreachable"

        class AgentSource:
            client_info = None

            async def get_agent(self, session):
                del session
                return agent

            async def get_deps(self, session, requested_agent):
                del session, requested_agent
                return None

            def get_runtime(self, session):
                del session
                toolsets = SimpleNamespace(all=[])
                return SimpleNamespace(deps=SimpleNamespace(toolsets=toolsets))

        adapter = AgentAcp(
            AgentSource(),
            config=AdapterConfig(
                session_store=MemorySessionStore(),
                enable_generic_tool_projection=False,
            ),
            usage_reporters=UsageReporterRegistry(),
        )
        harness = BlackBoxHarness(adapter=adapter)
        await harness.initialize()
        session = await harness.new_session(cwd=str(tmp_path))
        await harness.prompt_text(baseline_prompt)

        interrupted = asyncio.create_task(harness.prompt_text(action_prompt))
        await asyncio.wait_for(hold_started.wait(), timeout=5)
        await harness.adapter.cancel(session_id=session.session_id)
        response = await interrupted
        assert response.stop_reason == "cancelled"
        assert changes == ["applied"]

        await harness.prompt_text(follow_up_prompt)

        messages = follow_up_messages[0]
        assert any(
            isinstance(part, UserPromptPart) and part.content == baseline_prompt
            for message in messages
            for part in message.parts
        )
        action_prompt_count = sum(
            isinstance(part, UserPromptPart) and part.content == action_prompt
            for message in messages
            for part in message.parts
        )
        assert action_prompt_count == 1
        has_action_call = any(
            isinstance(part, ToolCallPart) and part.tool_call_id == "action-call"
            for message in messages
            for part in message.parts
        )
        has_action_result = any(
            isinstance(part, ToolReturnPart)
            and part.tool_call_id == "action-call"
            and part.content == "operation completed"
            for message in messages
            for part in message.parts
        )
        assert has_action_call and has_action_result

    asyncio.run(exercise())
