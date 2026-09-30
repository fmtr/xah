from xah import models


def test_luna_model_has_medium_reasoning_and_detailed_summary():
    luna = models.Luna()
    assert luna.override._settings.get("openai_reasoning_effort") == "medium"
    assert luna.override._settings.get("openai_reasoning_summary") == "detailed"


def test_available_models_are_declared_on_harness():
    from xah.harness.base import HarnessBase

    harness = HarnessBase()
    assert len(harness.models) == 1
    assert harness.models[0].model_id == "openai:gpt-5.6-luna"
