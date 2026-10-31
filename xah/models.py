from __future__ import annotations

from functools import cached_property
from typing import Any, ClassVar

from pydantic_acp import AdapterModel as AcpAdapterModel
from pydantic_ai import ModelSettings
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider


class AdapterModel(AcpAdapterModel):
    """Define an ACP model from shared configuration and an optional per-instance id."""

    NAME: ClassVar[str] = ""
    MODEL_CLASS: ClassVar[type[Model]] = OpenAIResponsesModel
    PROVIDER_CLASS: ClassVar = OpenAIProvider
    PROVIDER_NAME: ClassVar[str] = "openai"
    MODEL_SETTINGS: ClassVar[ModelSettings] = ModelSettings()
    MODEL_KWARGS: ClassVar[dict[str, Any]] = {}

    def __init__(self, id: str | None = None, *, settings: Any = None) -> None:
        self.settings = settings
        model_name = self.NAME if id is None else id
        model = self.model_class(
            model_name,
            provider=self.provider,
            settings=self.model_settings,
            **self.MODEL_KWARGS,
        )
        super().__init__(
            model_id=f"{self.PROVIDER_NAME}:{model_name}",
            name=model_name,
            override=model,
        )

    @cached_property
    def provider(self):
        return self.PROVIDER_CLASS(**self.provider_kwargs)

    @cached_property
    def provider_kwargs(self) -> dict[str, Any]:
        return {}

    @cached_property
    def model_settings(self) -> ModelSettings:
        return self.MODEL_SETTINGS

    @cached_property
    def model_class(self) -> type[Model]:
        return self.MODEL_CLASS

    @cached_property
    def model(self) -> Model:
        return self.override


class AdapterModelOpenAI(AdapterModel):
    """Configure models served by OpenAI's provider."""
    MODEL_SETTINGS = ModelSettings(
        openai_reasoning_effort="medium",
        openai_reasoning_summary="detailed",
    )

class Luna(AdapterModelOpenAI):
    NAME = "gpt-6-luna"

