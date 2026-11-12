import asyncio
import math
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.usage import RunUsage
from pydantic_ai_summarization import count_tokens_approximately

from xah.caps.context import AgentSummaryContextManager
from xah.server.acp.usage import UsageReporter, UsageReporterRegistry
from xah.toolsets.context.compact import Compact
from xah.toolsets.context.toolset import Context


def test_compact_requests_context_manager_compaction():
    context_manager = SimpleNamespace()
    context_manager.request_compact_with_summary = lambda summary: setattr(
        context_manager,
        "summary",
        summary,
    )
    ctx = RunContext(
        deps=SimpleNamespace(context_manager=context_manager),
        model=None,
        usage=RunUsage(),
    )
    toolset = Context()
    summary = "Synthetic summary payload for the test."

    result = asyncio.run(Compact(ctx=ctx, toolset=toolset, summary=summary).run())

    assert context_manager.summary == summary
    assert "supplied summary" in result


def test_compaction_removes_its_context_tool_exchange():
    context_manager = AgentSummaryContextManager(max_tokens=1000, compress_threshold=0.5)
    deps = SimpleNamespace(
        context_manager=context_manager,
        models=SimpleNamespace(current=SimpleNamespace(CONTEXT_COMPACTION_THRESHOLD=0.75)),
    )
    ctx = RunContext(deps=deps, model=None, usage=RunUsage())
    toolset = Context()
    summary = "Synthetic continuation summary for the next step."
    tool_name = Context.get_name(Compact)
    tool_call_id = "compact-call"
    tool_response = ModelResponse(
        parts=[
            ToolCallPart(
                tool_name=tool_name,
                args={"summary": summary},
                tool_call_id=tool_call_id,
            ),
        ],
    )

    tool_result = asyncio.run(Compact(ctx=ctx, toolset=toolset, summary=summary).run())
    request_context = SimpleNamespace(
        messages=[
            ModelRequest(parts=[UserPromptPart("Continue the synthetic task.")]),
            tool_response,
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name=tool_name,
                        content=tool_result,
                        tool_call_id=tool_call_id,
                    ),
                ],
            ),
        ],
    )

    asyncio.run(context_manager.before_model_request(ctx, request_context))

    messages = request_context.messages
    compact_tool_calls = [
        part
        for message in messages
        for part in message.parts
        if isinstance(part, ToolCallPart) and part.tool_name == tool_name
    ]
    compact_tool_returns = [
        part
        for message in messages
        for part in message.parts
        if isinstance(part, ToolReturnPart) and part.tool_name == tool_name
    ]
    assert context_manager.compression_count == 1
    assert any(
        isinstance(part, UserPromptPart) and summary in part.content
        for message in messages
        for part in message.parts
    )
    assert any(
        isinstance(part, UserPromptPart)
        and "The summary above is the current state. Continue the original task from here."
        in part.content
        for message in messages
        for part in message.parts
    )
    assert not compact_tool_calls and not compact_tool_returns, (
        compact_tool_calls,
        compact_tool_returns,
    )


@dataclass
class ContextManagerDeps:
    context_manager: AgentSummaryContextManager
    models: Any
    toolsets: Any


def test_compaction_history_is_replaced_before_the_next_tool_round():
    history = []
    for turn in range(12):
        task = f"Synthetic task update {turn}: inspect a module, preserve behavior, and continue. "
        evidence = f"Synthetic local fixture evidence {turn}; no production data. " * 60
        history.append(ModelRequest(parts=[UserPromptPart(task + evidence)]))
        result = f"Completed synthetic step {turn}; findings and next action recorded. "
        detail = f"Synthetic result {turn}: checked the call path and regression condition. " * 60
        history.append(ModelResponse(parts=[TextPart(result + detail)]))
    history.append(ModelRequest(parts=[UserPromptPart("Continue synthetic verification.")]))

    maximum = math.floor(count_tokens_approximately(history) / 0.78)
    toolset = Context()
    context_manager = AgentSummaryContextManager(max_tokens=maximum, compress_threshold=0.5)
    deps = ContextManagerDeps(
        context_manager=context_manager,
        models=SimpleNamespace(current=SimpleNamespace(CONTEXT_COMPACTION_THRESHOLD=0.75)),
        toolsets=SimpleNamespace(all=SimpleNamespace(cls={Context: toolset})),
    )
    summary = "Synthetic continuation summary preserving completed work and next verification. " * 60
    compact_tool_name = Context.get_name(Compact)
    advance_tool_name = "advance_synthetic_step"
    advance_tool_called = [False]
    requests = []

    def respond(messages, _agent_info):
        warning_percentages = [
            part.content.split("Context usage is ")[1].split("%")[0]
            for message in messages
            if isinstance(message, ModelRequest)
            for part in message.parts
            if isinstance(part, (SystemPromptPart, UserPromptPart))
            and "URGENT: Context usage" in part.content
        ]
        requests.append(
            (
                len(messages),
                warning_percentages,
                count_tokens_approximately(messages),
            ),
        )
        if warning_percentages and context_manager.compression_count < 2:
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name=compact_tool_name,
                        args={"summary": summary},
                        tool_call_id=f"compact-{len(requests)}",
                    ),
                ],
            )
        if context_manager.compression_count == 1 and not advance_tool_called[0]:
            advance_tool_called[0] = True
            return ModelResponse(
                parts=[
                    ToolCallPart(
                        tool_name=advance_tool_name,
                        args={},
                        tool_call_id="advance-synthetic-step",
                    ),
                ],
            )
        return ModelResponse(parts=[TextPart("Synthetic verification complete.")])

    agent = Agent(
        FunctionModel(respond),
        deps_type=ContextManagerDeps,
        capabilities=[context_manager],
        toolsets=[toolset],
    )

    @agent.tool_plain
    async def advance_synthetic_step() -> str:
        return "Small synthetic tool result; no production data."

    asyncio.run(agent.run("Continue synthetic verification.", deps=deps, message_history=history))

    assert requests[0][2] / maximum >= 0.75
    assert requests[1][2] / maximum < 0.75
    assert context_manager.compression_count == 1, requests
    assert len(requests) == 3, requests
    assert [request[1] for request in requests] == [["78"], [], []]
    assert requests[1][0] < requests[0][0]


def test_context_compaction_instructions_and_summary_requirements():
    warning = Context.COMPACTION_REQUIRED_MESSAGE.format(
        usage=0.8,
        toolset_name=Context.name,
        tool_name=Context.get_name(Compact),
    )
    normalized_warning = " ".join(warning.split())
    activation_instruction = f"Activate the {Context.name} toolset."
    definition_instruction = f"Carefully read the {Context.get_name(Compact)} tool definition"
    call_instruction = f"Then call {Context.get_name(Compact)}"
    assert normalized_warning.index(activation_instruction) < normalized_warning.index(
        definition_instruction
    ) < normalized_warning.index(call_instruction)
    summary_description = Compact.model_fields["summary"].description
    assert "500–1,000-word" in summary_description
    assert "URLs" in summary_description


def test_agent_summary_context_manager_replaces_history_without_summarizer(monkeypatch):
    changes = []
    context_manager = AgentSummaryContextManager(
        max_tokens=1000,
        token_counter=lambda messages: len(messages) * 100,
        on_before_compress=lambda messages, cutoff: changes.append(("before", cutoff)),
        on_after_compress=lambda messages, summarized, summary: changes.append(
            ("after", summarized, summary)
        ),
    )
    system = SystemPromptPart(content="Keep the harness instructions.")
    messages = [
        ModelRequest(parts=[system, UserPromptPart(content="Synthetic task alpha.")]),
        ModelResponse(parts=[TextPart(content="Synthetic step one complete.")]),
        ModelRequest(parts=[UserPromptPart(content="Continue synthetic task.")]),
    ]
    request_context = SimpleNamespace(messages=messages)
    summary = "Synthetic summary: step one complete; step two remains."

    async def unexpected_summary(*args, **kwargs):
        raise AssertionError("The supplied summary should bypass the summarization model.")

    assert context_manager._summarization_processor is not None
    monkeypatch.setattr(
        context_manager._summarization_processor,
        "_create_summary",
        unexpected_summary,
    )
    context_manager.request_compact_with_summary(summary)
    deps = SimpleNamespace(
        models=SimpleNamespace(
            current=SimpleNamespace(CONTEXT_COMPACTION_THRESHOLD=0.75),
        ),
    )
    ctx = RunContext(deps=deps, model=None, usage=RunUsage())

    asyncio.run(context_manager.before_model_request(ctx, request_context))

    compacted = request_context.messages
    assert len(compacted) == 2
    assert compacted[0].parts[0] == system
    assert compacted[0].parts[1].content.endswith(summary)
    assert compacted[1] == messages[2]
    assert changes == [("before", 2), ("after", True, summary)]
    assert context_manager.compression_count == 1


def test_usage_reporter_keeps_latest_context_usage():
    reporter = UsageReporter()
    reporter.begin(SimpleNamespace(context_window=1000))

    reporter.report(0.2, 200, 1000)
    reporter.report(0.1, 100, 1000)

    assert reporter.active_model.context_window == 1000
    assert reporter.used == 100
    assert reporter.size == 1000


def test_usage_reporters_are_independent_per_session():
    reporters = UsageReporterRegistry()
    first = reporters.for_session("session-1")
    second = reporters.for_session("session-2")

    first.report(0.2, 200, 1000)

    assert first is not second
    assert second.used is None
    assert second.size is None
