import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from openai import AsyncOpenAI
from pydantic_acp import AdapterConfig, BlackBoxHarness, MemorySessionStore
from pydantic_ai import Agent, ModelResponse
from pydantic_ai.messages import (
    ModelRequest,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

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


def test_cancelled_acp_history_omits_unavailable_responses_reasoning_item(tmp_path):
    async def exercise():
        missing_item_id = "rs_synthetic_cancelled_item"
        baseline_prompt = "Keep the baseline."
        action_prompt = "Record an observation, then wait."
        follow_up_prompt = "What happened before cancellation?"
        wait_started = asyncio.Event()
        side_effects = []
        requests = []
        cancelled = False

        def respond(request):
            body = json.loads(request.content)
            requests.append(body)
            input_items = body["input"]
            item_ids = {
                item.get("id") for item in input_items if isinstance(item, dict)
            }
            if cancelled and missing_item_id in item_ids:
                return httpx.Response(
                    404,
                    json={
                        "error": {
                            "message": f"Item with id '{missing_item_id}' not found.",
                            "type": "invalid_request_error",
                            "param": "input",
                            "code": None,
                        }
                    },
                )

            return httpx.Response(
                200,
                json={
                    "id": "resp_synthetic_follow_up",
                    "object": "response",
                    "created_at": 1_764_000_000,
                    "model": "synthetic-reasoner",
                    "output": [
                        {
                            "id": "msg_synthetic_follow_up",
                            "type": "message",
                            "role": "assistant",
                            "status": "completed",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "follow-up received",
                                    "annotations": [],
                                }
                            ],
                        }
                    ],
                    "parallel_tool_calls": True,
                    "tool_choice": "auto",
                    "tools": [],
                    "status": "completed",
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
            async with AsyncOpenAI(
                api_key="synthetic-test-key",
                http_client=http_client,
            ) as openai_client:
                responses_model = OpenAIResponsesModel(
                    "synthetic-reasoner",
                    provider=OpenAIProvider(openai_client=openai_client),
                    profile={"openai_supports_encrypted_reasoning_content": True},
                    settings={
                        "openai_reasoning_effort": "medium",
                        "openai_reasoning_summary": "detailed",
                    },
                )

                async def fake_model(messages, info):
                    latest_prompt = next(
                        part.content
                        for message in reversed(messages)
                        if isinstance(message, ModelRequest)
                        for part in reversed(message.parts)
                        if isinstance(part, UserPromptPart)
                    )
                    if latest_prompt == baseline_prompt:
                        return ModelResponse(
                            parts=[
                                ThinkingPart(
                                    "prior reasoning",
                                    id="rs_synthetic_prior_item",
                                    provider_name="openai",
                                ),
                                TextPart("baseline retained"),
                            ],
                            provider_name="openai",
                        )
                    if latest_prompt == follow_up_prompt:
                        return await responses_model.request(
                            messages,
                            info.model_settings,
                            info.model_request_parameters,
                        )

                    record_completed = any(
                        isinstance(part, ToolReturnPart)
                        and part.tool_name == "record_observation"
                        for message in messages
                        for part in message.parts
                    )
                    if record_completed:
                        return ModelResponse(
                            parts=[
                                ThinkingPart(
                                    "wait reasoning",
                                    id="rs_synthetic_wait_item",
                                    provider_name="openai",
                                ),
                                ToolCallPart(
                                    "wait_for_cancel",
                                    {},
                                    tool_call_id="call_wait",
                                ),
                            ],
                            provider_name="openai",
                        )

                    return ModelResponse(
                        parts=[
                            ThinkingPart(
                                "record reasoning",
                                id=missing_item_id,
                                provider_name="openai",
                            ),
                            ToolCallPart(
                                "record_observation",
                                {},
                                tool_call_id="call_record",
                            ),
                        ],
                        provider_name="openai",
                    )

                agent = Agent(FunctionModel(fake_model), output_type=str)

                @agent.tool_plain
                async def record_observation() -> str:
                    side_effects.append("recorded")
                    return "operation completed"

                @agent.tool_plain
                async def wait_for_cancel() -> str:
                    wait_started.set()
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
                await asyncio.wait_for(wait_started.wait(), timeout=5)
                cancelled = True
                await harness.adapter.cancel(session_id=session.session_id)
                response = await interrupted

                assert response.stop_reason == "cancelled"
                assert side_effects == ["recorded"]

                await harness.prompt_text(follow_up_prompt)

                input_items = requests[0]["input"]
                item_ids = {
                    item.get("id") for item in input_items if isinstance(item, dict)
                }
                assert "rs_synthetic_prior_item" in item_ids
                assert missing_item_id not in item_ids
                assert "rs_synthetic_wait_item" not in item_ids
                assert any(
                    item.get("call_id") == "call_record"
                    for item in input_items
                    if isinstance(item, dict)
                )

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "response_part_order",
    [
        ("thinking", "message", "tool_call"),
        ("thinking", "tool_call", "message"),
        ("message", "thinking", "tool_call"),
        ("message", "tool_call", "thinking"),
        ("tool_call", "thinking", "message"),
        ("tool_call", "message", "thinking"),
    ],
)
def test_cancelled_acp_history_avoids_orphaned_responses_items(tmp_path, response_part_order):
    async def exercise():
        reasoning_id = "rs_synthetic_empty_summary"
        message_id = "msg_synthetic_empty_summary"
        function_item_id = "fc_synthetic_empty_summary"
        tool_call_id = "call_synthetic_empty_summary"
        wait_reasoning_id = "rs_synthetic_wait"
        wait_function_item_id = "fc_synthetic_wait"
        wait_tool_call_id = "call_synthetic_wait"
        action_prompt = "Carry out the sample operation."
        follow_up_prompt = "Report on the interrupted operation."
        assistant_update = "A brief update before the operation."
        wait_started = asyncio.Event()
        requests = []
        tool_effects = []

        def respond(request):
            request_body = json.loads(request.content)
            requests.append(request_body)
            input_items = request_body["input"]
            has_function_call = any(
                isinstance(item, dict)
                and item.get("type") == "function_call"
                and item.get("id") == function_item_id
                for item in input_items
            )
            has_reasoning_item = any(
                isinstance(item, dict)
                and item.get("type") == "reasoning"
                and item.get("id") == reasoning_id
                for item in input_items
            )
            has_message_item = any(
                isinstance(item, dict)
                and item.get("type") == "message"
                and item.get("id") == message_id
                for item in input_items
            )
            if has_message_item and not has_reasoning_item:
                return httpx.Response(
                    400,
                    json={
                        "error": {
                            "message": (
                                f"Item '{message_id}' of type 'message' was provided "
                                f"without its required 'reasoning' item: '{reasoning_id}'."
                            ),
                            "type": "invalid_request_error",
                            "param": "input",
                            "code": None,
                        }
                    },
                )

            if has_function_call and not has_reasoning_item:
                return httpx.Response(
                    400,
                    json={
                        "error": {
                            "message": "orphan function call",
                            "type": "invalid_request_error",
                            "param": "input",
                            "code": None,
                        }
                    },
                )

            return httpx.Response(
                200,
                json={
                    "id": "resp_synthetic_success",
                    "object": "response",
                    "created_at": 1_764_000_000,
                    "model": "synthetic-reasoner",
                    "output": [
                        {
                            "id": "msg_synthetic_success",
                            "type": "message",
                            "role": "assistant",
                            "status": "completed",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "operation acknowledged",
                                    "annotations": [],
                                }
                            ],
                        }
                    ],
                    "parallel_tool_calls": True,
                    "tool_choice": "auto",
                    "tools": [],
                    "status": "completed",
                },
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http_client:
            async with AsyncOpenAI(
                api_key="synthetic-test-key",
                http_client=http_client,
            ) as openai_client:
                responses_model = OpenAIResponsesModel(
                    "synthetic-reasoner",
                    provider=OpenAIProvider(openai_client=openai_client),
                    profile={"openai_supports_encrypted_reasoning_content": True},
                    settings={
                        "openai_reasoning_effort": "medium",
                        "openai_reasoning_summary": "detailed",
                    },
                )

                async def respond_from_agent(messages, info):
                    latest_prompt = next(
                        part.content
                        for message in reversed(messages)
                        if isinstance(message, ModelRequest)
                        for part in reversed(message.parts)
                        if isinstance(part, UserPromptPart)
                    )
                    if latest_prompt == follow_up_prompt:
                        return await responses_model.request(
                            messages,
                            info.model_settings,
                            info.model_request_parameters,
                        )

                    operation_completed = any(
                        isinstance(part, ToolReturnPart) and part.tool_name == "sample_operation"
                        for message in messages
                        for part in message.parts
                    )
                    if operation_completed:
                        return ModelResponse(
                            parts=[
                                ThinkingPart(
                                    "",
                                    id=wait_reasoning_id,
                                    signature="synthetic-wait-signature",
                                    provider_name="openai",
                                ),
                                ToolCallPart(
                                    "wait_for_cancel",
                                    {},
                                    tool_call_id=wait_tool_call_id,
                                    id=wait_function_item_id,
                                    provider_name="openai",
                                ),
                            ],
                            provider_name="openai",
                        )

                    response_parts = {
                        "thinking": ThinkingPart(
                            "",
                            id=reasoning_id,
                            signature="synthetic-encrypted-reasoning",
                            provider_name="openai",
                        ),
                        "message": TextPart(
                            assistant_update,
                            id=message_id,
                            provider_name="openai",
                        ),
                        "tool_call": ToolCallPart(
                            "sample_operation",
                            {},
                            tool_call_id=tool_call_id,
                            id=function_item_id,
                            provider_name="openai",
                        ),
                    }
                    return ModelResponse(
                        parts=[response_parts[kind] for kind in response_part_order],
                        provider_name="openai",
                    )

                agent = Agent(FunctionModel(respond_from_agent), output_type=str)

                @agent.tool_plain
                async def sample_operation() -> str:
                    tool_effects.append("recorded")
                    return "operation completed"

                @agent.tool_plain
                async def wait_for_cancel() -> str:
                    wait_started.set()
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
                interrupted = asyncio.create_task(harness.prompt_text(action_prompt))
                await asyncio.wait_for(wait_started.wait(), timeout=5)
                await harness.adapter.cancel(session_id=session.session_id)
                response = await interrupted

                assert response.stop_reason == "cancelled"
                assert tool_effects == ["recorded"]
                await harness.prompt_text(follow_up_prompt)

                input_items = requests[0]["input"]
                assert any(
                    isinstance(item, dict)
                    and item.get("role") == "assistant"
                    and item.get("content") == assistant_update
                    for item in input_items
                )
                assert any(
                    isinstance(item, dict)
                    and item.get("type") == "function_call"
                    and item.get("call_id") == tool_call_id
                    for item in input_items
                )
                assert not any(
                    isinstance(item, dict) and item.get("id") == function_item_id
                    for item in input_items
                )
                assert not any(
                    isinstance(item, dict)
                    and item.get("type") == "reasoning"
                    and item.get("id") == reasoning_id
                    for item in input_items
                )
                assert any(
                    isinstance(item, dict)
                    and item.get("type") == "function_call_output"
                    and item.get("call_id") == tool_call_id
                    for item in input_items
                )

    asyncio.run(exercise())
