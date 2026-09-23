import json
import re
from dataclasses import dataclass, field
from typing import Any, ClassVar

from pydantic_ai import ModelMessagesTypeAdapter, RunContext
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import (
    FunctionToolResultEvent,
    InstructionPart,
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
)
from pydantic_ai.models import ModelRequestContext
from pydantic_deep import DeepAgentDeps

from corio import logs, yml
from corio.jsn import to_json
from xah.constants import TODO_STATE_END, TODO_STATE_START
from xah.obs import logger


TODO_STATE_PATTERN = re.compile(
    f"{re.escape(TODO_STATE_START)}(.*?){re.escape(TODO_STATE_END)}",
    re.DOTALL,
)
UNREADABLE_CHARACTER_PATTERN = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\ufeff]")


@dataclass(frozen=True)
class StructuredDataDeserializer:
    value: Any

    @property
    def data(self) -> Any:
        if self.is_binary:
            return self.binary_data
        if isinstance(self.value, dict):
            return {key: type(self)(value).data for key, value in self.value.items()}
        if isinstance(self.value, list | tuple):
            return [type(self)(value).data for value in self.value]
        if isinstance(self.value, str):
            return self.decoded_string
        return self.value

    @property
    def is_binary(self) -> bool:
        return isinstance(self.value, dict) and self.value.get("kind") == "binary"

    @property
    def binary_data(self) -> dict[str, Any]:
        encoded = self.value["data"]
        byte_count = (len(encoded) * 3) // 4 - encoded.count("=")
        return {
            "kind": "binary",
            "media_type": self.value["media_type"],
            "bytes": byte_count,
            "identifier": self.value["identifier"],
        }

    @property
    def decoded_string(self) -> Any:
        value = self.value
        while isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return value

        if isinstance(value, dict | list):
            return type(self)(value).data
        return self.value


@dataclass(frozen=True)
class PartDeserializer:
    source: dict[str, Any]

    fields: ClassVar[tuple[str, ...]] = ("content",)
    ignored_fields: ClassVar[frozenset[str]] = frozenset(
        {
            "id",
            "provider_details",
            "provider_name",
            "signature",
            "timestamp",
        }
    )

    @classmethod
    def from_source(cls, source: dict[str, Any]) -> "PartDeserializer":
        deserializer = cls.deserializers.get(source["part_kind"], GenericPartDeserializer)
        return deserializer(source)

    deserializers: ClassVar[dict[str, type["PartDeserializer"]]]

    @property
    def kind(self) -> str:
        return self.source["part_kind"]

    @property
    def data(self) -> dict[str, Any]:
        data = {"kind": self.kind}
        data.update(self.selected_data)
        return data

    @property
    def selected_data(self) -> dict[str, Any]:
        return {
            name: StructuredDataDeserializer(self.source[name]).data
            for name in self.fields
            if name in self.source
        }


@dataclass(frozen=True)
class ToolPartDeserializer(PartDeserializer):
    fields: ClassVar[tuple[str, ...]] = ("tool_name", "tool_call_id")


@dataclass(frozen=True)
class ToolCallDeserializer(ToolPartDeserializer):
    fields: ClassVar[tuple[str, ...]] = (*ToolPartDeserializer.fields, "args")


@dataclass(frozen=True)
class ToolResultDeserializer(ToolPartDeserializer):
    fields: ClassVar[tuple[str, ...]] = (*ToolPartDeserializer.fields, "outcome", "content")


@dataclass(frozen=True)
class GenericPartDeserializer(PartDeserializer):
    @property
    def selected_data(self) -> dict[str, Any]:
        return {
            name: StructuredDataDeserializer(value).data
            for name, value in self.source.items()
            if name != "part_kind" and name not in self.ignored_fields
        }


PartDeserializer.deserializers = {
    "builtin-tool-call": ToolCallDeserializer,
    "builtin-tool-return": ToolResultDeserializer,
    "retry-prompt": ToolResultDeserializer,
    "tool-call": ToolCallDeserializer,
    "tool-return": ToolResultDeserializer,
}


@dataclass(frozen=True)
class MessageDeserializer:
    messages: list[ModelMessage]

    @property
    def serialized_messages(self) -> list[dict[str, Any]]:
        return ModelMessagesTypeAdapter.dump_python(self.messages, mode="json", exclude_none=True)

    @property
    def current_request_messages(self) -> list[dict[str, Any]]:
        current: list[dict[str, Any]] = []
        for message in reversed(self.serialized_messages):
            if message["kind"] == "response":
                break
            current.append(message)
        return list(reversed(current))

    @property
    def current_request_parts(self) -> list[dict[str, Any]]:
        return self.parts(self.current_request_messages)

    @classmethod
    def parts(cls, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            PartDeserializer.from_source(part).data
            for message in messages
            for part in message["parts"]
        ]


@dataclass(frozen=True)
class ResponseDeserializer(MessageDeserializer):
    @property
    def response_parts(self) -> list[dict[str, Any]]:
        return self.parts(self.serialized_messages)


@dataclass(frozen=True)
class EventPartDeserializer:
    part: ModelRequestPart

    @property
    def data(self) -> dict[str, Any]:
        message = ModelRequest(parts=[self.part])
        source = ModelMessagesTypeAdapter.dump_python([message], mode="json", exclude_none=True)[0]["parts"][0]
        return PartDeserializer.from_source(source).data


@dataclass(frozen=True)
class SetupSnapshot:
    instructions: str
    tools: tuple[str, ...]
    todos: str

    @classmethod
    def from_context(cls, request_context: ModelRequestContext) -> "SetupSnapshot":
        parameters = request_context.model_request_parameters
        parts = parameters.instruction_parts or []
        instructions = InstructionDeserializer(parts)
        return cls(
            instructions=instructions.instructions,
            tools=tuple(sorted(parameters.tool_defs)),
            todos=instructions.todos,
        )

    def changes(self, previous: "SetupSnapshot | None") -> dict[str, Any]:
        if previous is None:
            return self.initial_data
        changes: dict[str, Any] = {}
        if self.instructions != previous.instructions:
            changes["instructions"] = self.instructions
        if self.tools != previous.tools:
            changes["tools"] = list(self.tools)
        if self.todos != previous.todos:
            changes["todos"] = self.todos
        return changes

    @property
    def initial_data(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if self.instructions:
            data["instructions"] = self.instructions
        if self.tools:
            data["tools"] = list(self.tools)
        if self.todos:
            data["todos"] = self.todos
        return data


@dataclass(frozen=True)
class InstructionDeserializer:
    parts: list[InstructionPart]

    @property
    def instruction_texts(self) -> tuple[str, ...]:
        texts = [self.instruction_content(part) for part in self.parts]
        return tuple(text for text in texts if text)

    @property
    def instructions(self) -> str:
        texts = tuple(dict.fromkeys(self.instruction_texts))
        texts = tuple(
            text
            for text in texts
            if not any(text != other and text in other for other in texts)
        )
        return "\n\n".join(texts)

    @property
    def todos(self) -> str:
        blocks = [
            match.group(1).strip()
            for part in self.parts
            for match in TODO_STATE_PATTERN.finditer(part.content)
            if match.group(1).strip()
        ]
        return "\n\n".join(blocks)

    @staticmethod
    def instruction_content(part: InstructionPart) -> str:
        content = TODO_STATE_PATTERN.sub("", part.content)
        return re.sub(r"\n{3,}", "\n\n", content).strip()

@dataclass
class SetupTracker:
    snapshot: SetupSnapshot | None = None


@dataclass
class ModelTrafficLogger(AbstractCapability[DeepAgentDeps]):
    label: str
    setup_tracker: SetupTracker = field(default_factory=SetupTracker)
    request_signature: str | None = None
    pending_event_parts: set[str] = field(default_factory=set)

    async def for_run(self, ctx: RunContext[DeepAgentDeps]) -> "ModelTrafficLogger":
        return type(self)(label=self.label, setup_tracker=self.setup_tracker)

    @staticmethod
    def readable_payload(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: ModelTrafficLogger.readable_payload(item) for key, item in value.items()}
        if isinstance(value, list):
            return [ModelTrafficLogger.readable_payload(item) for item in value]
        if not isinstance(value, str):
            return value

        if "\n" not in value and "\\n" in value:
            value = value.replace("\\r\\n", "\n").replace("\\n", "\n")

        value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")
        value = "\n".join(line.rstrip() for line in value.split("\n"))
        return UNREADABLE_CHARACTER_PATTERN.sub("�", value)

    def log_payload(self, payload: dict[str, Any]) -> None:
        payload = self.readable_payload(payload)
        message = yml.to_yaml({"agent": self.label, **payload})
        logger.info(logs.sanitize(message))

    def log_setup(self, request_context: ModelRequestContext) -> None:
        snapshot = SetupSnapshot.from_context(request_context)
        changes = snapshot.changes(self.setup_tracker.snapshot)
        self.setup_tracker.snapshot = snapshot
        if changes:
            self.log_payload({"event": "setup", **changes})

    def log_request(self, request_context: ModelRequestContext) -> None:
        message = MessageDeserializer(request_context.messages)
        parts = self.unlogged_request_parts(message)
        signature = to_json(parts)
        if self.request_signature == signature:
            return
        self.request_signature = signature
        if parts:
            self.log_payload(
                {
                    "event": "model-request",
                    "model": request_context.model.model_name,
                    "messages": parts,
                }
            )

    def unlogged_request_parts(self, message: MessageDeserializer) -> list[dict[str, Any]]:
        parts: list[dict[str, Any]] = []
        for part in message.current_request_parts:
            signature = to_json(part)
            if signature in self.pending_event_parts:
                self.pending_event_parts.remove(signature)
                continue
            parts.append(part)
        return parts

    def log_response(self, response: ModelResponse) -> None:
        message = ResponseDeserializer([response])
        self.log_payload(
            {
                "event": "model-response",
                "model": response.model_name,
                "messages": message.response_parts,
            }
        )

    async def wrap_model_request(
        self,
        ctx: RunContext[DeepAgentDeps],
        *,
        request_context: ModelRequestContext,
        handler,
    ) -> ModelResponse:
        self.log_setup(request_context)
        self.log_request(request_context)
        response = await handler(request_context)
        self.log_response(response)
        self.request_signature = None
        return response

    async def wrap_run_event_stream(self, ctx: RunContext[DeepAgentDeps], *, stream):
        async for event in stream:
            if isinstance(event, FunctionToolResultEvent):
                self.log_event_part(event)
            yield event

    def log_event_part(self, event: FunctionToolResultEvent) -> None:
        part = EventPartDeserializer(event.part).data
        signature = to_json(part)
        if signature in self.pending_event_parts:
            return
        self.pending_event_parts.add(signature)
        self.log_payload({"event": "tool-result", **part})
