import asyncio
from types import SimpleNamespace

from pydantic_ai import RunContext
from pydantic_ai.usage import RunUsage

from xah.server.acp.usage import UsageReporter, UsageReporterRegistry
from xah.toolsets.context.compact import Compact
from xah.toolsets.context.toolset import Context


def test_compact_requests_context_manager_compaction():
    context_manager = SimpleNamespace()
    context_manager.request_compact = lambda *, focus: setattr(
        context_manager,
        "focus",
        focus,
    )
    ctx = RunContext(
        deps=SimpleNamespace(context_manager=context_manager),
        model=None,
        usage=RunUsage(),
    )
    toolset = Context()

    result = asyncio.run(Compact(ctx=ctx, toolset=toolset, focus="the goal").run())

    assert context_manager.focus == "the goal"
    assert "Focus: the goal" in result


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
