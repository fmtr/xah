from pydantic_acp import AdapterModel
from pydantic_ai import ModelSettings
from pydantic_ai.models.openai import OpenAIResponsesModel


LUNA_MODEL_NAME = "gpt-5.6-luna"
LUNA_ID = f"openai:{LUNA_MODEL_NAME}"

luna = OpenAIResponsesModel(
    LUNA_MODEL_NAME,
    settings=ModelSettings(
        openai_reasoning_effort="medium",
        openai_reasoning_summary="detailed",
    ),
)

models: list[AdapterModel] = [
    AdapterModel(model_id=LUNA_ID, name=LUNA_MODEL_NAME, override=luna),
]
