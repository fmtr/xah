from xah import models


def test_luna_model_has_medium_reasoning_and_detailed_summary():
    luna = models.Luna()
    assert luna.override._settings.get("openai_reasoning_effort") == "medium"
    assert luna.override._settings.get("openai_reasoning_summary") == "detailed"


def test_available_models_are_declared_on_harness():
    from types import SimpleNamespace

    from xah.harness.base import HarnessAcp
    from xah.server.acp.usage import UsageReporterRegistry

    harness = HarnessAcp(
        session=SimpleNamespace(cwd=".", session_id="test-session"),
        usage_reporters=UsageReporterRegistry(),
    )
    assert len(harness.models) == 1
    assert harness.models[0].model_id == "openai:gpt-5.6-luna"
