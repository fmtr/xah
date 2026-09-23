from xah import models


def test_luna_model_has_medium_reasoning_and_detailed_summary():
    assert models.luna._settings.get("openai_reasoning_effort") == "medium"
    assert models.luna._settings.get("openai_reasoning_summary") == "detailed"
def test_available_models_contains_luna():
    assert isinstance(models.models, list)
    assert len(models.models) == 1
    assert next(item for item in models.models if item.model_id == "openai:gpt-5.6-luna").override is models.luna
