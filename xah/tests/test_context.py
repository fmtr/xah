import asyncio
from types import SimpleNamespace

from pydantic_ai import RunContext
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.usage import RunUsage

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


def test_context_manager_warns_once_per_above_threshold_episode(monkeypatch):
    warnings = []
    context_toolset = SimpleNamespace(
        feedback=lambda ctx, message: warnings.append(message),
    )
    deps = SimpleNamespace(
        models=SimpleNamespace(
            current=SimpleNamespace(CONTEXT_COMPACTION_THRESHOLD=0.75),
        ),
        toolsets=SimpleNamespace(all=SimpleNamespace(cls={Context: context_toolset})),
    )
    token_count = {"value": 800}
    context_manager = AgentSummaryContextManager(
        max_tokens=1000,
        compress_threshold=0.5,
        token_counter=lambda messages: token_count["value"],
    )
    messages = [
        ModelRequest(parts=[UserPromptPart(content="Synthetic task alpha.")]),
        ModelResponse(parts=[TextPart(content="Synthetic step one complete.")]),
        ModelRequest(parts=[UserPromptPart(content="Continue synthetic task.")]),
    ]
    request_context = SimpleNamespace(messages=messages)
    ctx = RunContext(deps=deps, model=None, usage=RunUsage())

    async def unexpected_summary(*args, **kwargs):
        raise AssertionError("Threshold warnings must not invoke a secondary summarizer.")

    assert context_manager._summarization_processor is not None
    monkeypatch.setattr(
        context_manager._summarization_processor,
        "_create_summary",
        unexpected_summary,
    )

    asyncio.run(context_manager.before_model_request(ctx, request_context))
    asyncio.run(context_manager.before_model_request(ctx, request_context))
    assert len(warnings) == 2

    summary = "Synthetic summary: step one complete; step two remains."
    context_manager.request_compact_with_summary(summary)
    asyncio.run(context_manager.before_model_request(ctx, request_context))
    compacted = request_context.messages
    assert len(compacted) == 2
    assert compacted[0].parts[-1].content.endswith(summary)
    assert context_manager.compression_count == 1
    assert len(warnings) == 2

    asyncio.run(context_manager.before_model_request(ctx, request_context))
    assert len(warnings) == 2

    token_count["value"] = 500
    asyncio.run(context_manager.before_model_request(ctx, request_context))
    token_count["value"] = 800
    asyncio.run(context_manager.before_model_request(ctx, request_context))

    warning = Context.COMPACTION_REQUIRED_MESSAGE.format(
        usage=0.8,
        toolset_name=Context.name,
        tool_name=Context.get_name(Compact),
    )
    assert "500–1,000-word" not in warning
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
    assert warnings == [warning, warning, warning]
    assert request_context.messages is compacted


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
