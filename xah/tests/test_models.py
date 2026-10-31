import sys

from xah import models


def test_model_adapters_accept_model_id_without_a_model_class():
    adapter = models.AdapterModelOpenAI(id="gpt-test")

    assert adapter.model_id == "openai:gpt-test"
    assert adapter.name == "gpt-test"
    assert adapter.override.model_name == "gpt-test"


def test_luna_model_has_medium_reasoning_and_detailed_summary():
    luna = models.Luna()
    assert luna.override._settings.get("openai_reasoning_effort") == "medium"
    assert luna.override._settings.get("openai_reasoning_summary") == "detailed"


def test_available_models_are_declared_on_harness(monkeypatch):
    monkeypatch.setattr(sys, "argv", [sys.argv[0]])
    from types import SimpleNamespace

    from xah.harness.base import HarnessAcp
    from xah.server.acp.usage import UsageReporterRegistry

    harness = HarnessAcp(
        session=SimpleNamespace(cwd=".", session_id="test-session"),
        usage_reporters=UsageReporterRegistry(),
    )
    assert harness.Models[0] is models.Luna
    assert len(harness.models) == 1
    assert harness.models[0].model_id == "openai:gpt-6-luna"
    assert harness.models[0].settings is harness.settings
