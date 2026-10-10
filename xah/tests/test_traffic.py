import asyncio
import json
from types import SimpleNamespace

from pydantic_ai import Agent
from pydantic_ai.messages import (
    BinaryContent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    InstructionPart,
    ModelRequest,
    ModelResponse,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel

from corio import yml
from xah.caps.traffic import InstructionDeserializer, ModelTrafficLogger
from xah.harness.base import Harness


def captured_logger(monkeypatch):
    capability = ModelTrafficLogger(label="root")
    captured = []
    monkeypatch.setattr("xah.caps.traffic.logs.sanitize", lambda value: value)
    monkeypatch.setattr(
        "xah.caps.traffic.logger.info",
        lambda message, **attributes: captured.append(attributes.get("payload", message)),
    )
    return capability, captured


def test_model_traffic_logger_logs_every_message_once(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    request = ModelRequest(parts=[UserPromptPart('{"task": "fix it"}')])
    response = ModelResponse(
        parts=[
            ThinkingPart("Inspecting the logger."),
            ToolCallPart(
                tool_name="write_file",
                args=json.dumps(json.dumps({"path": "traffic.py"})),
                tool_call_id="call-1",
            ),
        ],
        model_name="test-model",
    )
    final_response = ModelResponse(parts=[TextPart("Done.")], model_name="test-model")
    responses = iter([response, final_response])
    request_context = SimpleNamespace(
        messages=[request],
        model=SimpleNamespace(model_name="test-model"),
        model_request_parameters=SimpleNamespace(instruction_parts=[], tool_defs={}),
    )
    ctx = SimpleNamespace(run_id="run-1")

    async def handler(context):
        return next(responses)

    async def stream():
        yield FunctionToolCallEvent(response.parts[1])
        result = FunctionToolResultEvent(
            ToolReturnPart(
                tool_name="write_file",
                content='{"changed": true, "lines": "[1, 2]"}',
                tool_call_id="call-1",
            )
        )
        yield result
        yield result

    async def run():
        await capability.wrap_model_request(ctx, request_context=request_context, handler=handler)
        async for _ in capability.wrap_run_event_stream(ctx, stream=stream()):
            pass
        request_context.messages = [
            request,
            response,
            ModelRequest(
                parts=[
                    ToolReturnPart(
                        tool_name="write_file",
                        content='{"changed": true, "lines": "[1, 2]"}',
                        tool_call_id="call-1",
                    )
                ]
            ),
        ]
        await capability.wrap_model_request(ctx, request_context=request_context, handler=handler)

    asyncio.run(run())

    assert [yml.from_yaml(item) for item in captured] == [
        {
            "agent": "root",
            "event": "model-request",
            "model": "test-model",
            "messages": [{"kind": "user-prompt", "content": {"task": "fix it"}}],
        },
        {
            "agent": "root",
            "event": "model-response",
            "model": "test-model",
            "messages": [
                {"kind": "thinking", "content": "Inspecting the logger."},
                {
                    "kind": "tool-call",
                    "tool_name": "write_file",
                    "tool_call_id": "call-1",
                    "args": {"path": "traffic.py"},
                },
            ],
        },
        {
            "agent": "root",
            "event": "tool-result",
            "kind": "tool-return",
            "tool_name": "write_file",
            "tool_call_id": "call-1",
            "outcome": "success",
            "content": {"changed": True, "lines": [1, 2]},
        },
        {
            "agent": "root",
            "event": "model-response",
            "model": "test-model",
            "messages": [{"kind": "text", "content": "Done."}],
        },
    ]


def test_model_traffic_logger_logs_compacted_history(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    harness = Harness.__new__(Harness)
    harness.__dict__["model_traffic_logger"] = capability
    harness.__dict__["session_usage_reporter"] = SimpleNamespace(report=lambda *_: None)
    compressed = []
    harness.__dict__["deps"] = SimpleNamespace(after_compress=lambda: compressed.append(True))
    context_manager = harness.context_manager
    context_manager.max_tokens = 100_000
    context_manager._resolved_max_tokens = 100_000
    context_manager._summarization_processor.max_input_tokens = 100_000
    context_manager._summarization_processor._summarization_agent = Agent(
        TestModel(custom_output_text="Preserve the original task and its decision."),
    )
    context_manager.request_compact(focus="the original task")

    old_request = ModelRequest(parts=[UserPromptPart("The original task was to fix the logger.")])
    old_response = ModelResponse(parts=[TextPart("I inspected the logger.")], model_name="test-model")
    current_request = ModelRequest(parts=[UserPromptPart("Continue fixing it.")])
    request_context = SimpleNamespace(
        messages=[old_request, old_response, current_request],
        model=SimpleNamespace(model_name="test-model"),
    )

    async def run():
        await context_manager.before_model_request(SimpleNamespace(), request_context)

    asyncio.run(run())

    entries = [yml.from_yaml(item) for item in captured]
    compactions = [entry for entry in entries if entry["event"] == "context-compaction"]
    assert len(compactions) == 1
    assert compactions[0]["summary"] == "Preserve the original task and its decision."
    assert compressed == [True]
    messages = compactions[0]["messages"]
    assert len(messages) == 2
    assert messages[0]["kind"] == "request"
    assert messages[0]["parts"][0]["part_kind"] == "user-prompt"
    assert messages[0]["parts"][0]["content"].endswith(
        "Preserve the original task and its decision."
    )
    assert messages[1]["kind"] == "request"
    assert messages[1]["parts"][0]["part_kind"] == "user-prompt"
    assert messages[1]["parts"][0]["content"] == "Continue fixing it."


def test_model_traffic_logger_does_not_log_failed_compaction(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    capability.log_compaction(
        [ModelRequest(parts=[UserPromptPart("unchanged")])],
        False,
        None,
    )

    assert captured == []


def test_model_traffic_logger_suppresses_retried_request(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    request_context = SimpleNamespace(
        messages=[ModelRequest(parts=[UserPromptPart("same request")])],
        model=SimpleNamespace(model_name="test-model"),
        model_request_parameters=SimpleNamespace(instruction_parts=[], tool_defs={}),
    )

    capability.log_request(request_context)
    capability.log_request(request_context)

    assert len(captured) == 1


def test_model_traffic_logger_keeps_tool_result_without_live_event(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    request_context = SimpleNamespace(
        messages=[
            ModelResponse(
                parts=[ToolCallPart("read_file", {"path": "notes.txt"}, tool_call_id="resumed-call")]
            ),
            ModelRequest(
                parts=[ToolReturnPart("read_file", '{"content": "hello"}', tool_call_id="resumed-call")]
            ),
        ],
        model=SimpleNamespace(model_name="test-model"),
    )

    capability.log_request(request_context)

    entry = yml.from_yaml(captured[0])
    assert entry["messages"] == [
        {
            "kind": "tool-return",
            "tool_name": "read_file",
            "tool_call_id": "resumed-call",
            "outcome": "success",
            "content": {"content": "hello"},
        }
    ]


def test_model_traffic_logger_decodes_json_encoded_multiline_tool_result(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    content = "diff --git a/file b/file\n@@ -1 +1 @@\n-old\n+new\n"
    request_context = SimpleNamespace(
        messages=[
            ModelRequest(
                parts=[ToolReturnPart("git", json.dumps(content), tool_call_id="git-call")]
            )
        ],
        model=SimpleNamespace(model_name="test-model"),
    )

    capability.log_request(request_context)

    assert "content: |" in captured[0]
    assert yml.from_yaml(captured[0])["messages"][0]["content"] == content


def test_model_traffic_logger_renders_escaped_multiline_content(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    escaped = "diff --git a/file b/file\\n@@ -1 +1 @@\\n-old\\n+new\\n"
    expected = "diff --git a/file b/file\n@@ -1 +1 @@\n-old\n+new\n"

    capability.log_payload({"content": escaped})

    assert "content: |" in captured[0]
    assert yml.from_yaml(captured[0])["content"] == expected


def test_model_traffic_logger_sanitizes_git_diff_control_characters(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    content = "diff --git a/file b/file\r\n-old\tvalue\x00\r\n+new\tvalue\r\n"
    expected = "diff --git a/file b/file\n-old    value�\n+new    value\n"

    capability.log_payload({"content": content})

    assert "content: |" in captured[0]
    assert yml.from_yaml(captured[0])["content"] == expected


def test_model_traffic_logger_strips_trailing_whitespace_for_literal_yaml(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    content = "diff --git a/file b/file  \n@@ -1 +1 @@\n-old\n+new\n"
    expected = "diff --git a/file b/file\n@@ -1 +1 @@\n-old\n+new\n"

    capability.log_payload({"content": content})

    assert "content: |" in captured[0]
    assert yml.from_yaml(captured[0])["content"] == expected


def test_model_traffic_logger_summarizes_binary_content(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    content = BinaryContent(data=b"large binary payload", media_type="application/octet-stream")
    request_context = SimpleNamespace(
        messages=[ModelRequest(parts=[UserPromptPart([content])])],
        model=SimpleNamespace(model_name="test-model"),
    )

    capability.log_request(request_context)

    binary = yml.from_yaml(captured[0])["messages"][0]["content"][0]
    assert binary == {
        "kind": "binary",
        "media_type": "application/octet-stream",
        "bytes": len(content.data),
        "identifier": content.identifier,
    }


def test_model_traffic_logger_logs_setup_only_when_changed(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    request_context = SimpleNamespace(
        model_request_parameters=SimpleNamespace(
            instruction_parts=[
                InstructionPart(content="Complete the task."),
                InstructionPart(content="Complete the task. Use the relevant skills."),
                InstructionPart(content="<todo-state>\n- [ ] inspect\n- [ ] fix\n</todo-state>", dynamic=True),
            ],
            tool_defs={"read_todos": object(), "update_todo_status": object()},
        ),
    )

    capability.log_setup(request_context)
    capability.log_setup(request_context)
    request_context.model_request_parameters = SimpleNamespace(
        instruction_parts=[
            InstructionPart(content="Complete the task. Use the relevant skills."),
            InstructionPart(content="<todo-state>\n</todo-state>", dynamic=True),
        ],
        tool_defs={"read_todos": object(), "update_todo_status": object()},
    )
    capability.log_setup(request_context)

    assert [yml.from_yaml(item) for item in captured] == [
        {
            "agent": "root",
            "event": "setup",
            "instructions": "Complete the task. Use the relevant skills.",
            "tools": ["read_todos", "update_todo_status"],
            "todos": "- [ ] inspect\n- [ ] fix",
        },
        {
            "agent": "root",
            "event": "setup",
            "todos": "",
        },
    ]


def test_instruction_deserializer_extracts_todos_from_mixed_content():
    deserializer = InstructionDeserializer(
        [
            InstructionPart(
                content=(
                    "## Tool instructions\n"
                    "Use the tools carefully.\n\n"
                    "<todo-state>\n"
                    "- [*] [abc123] Inspect the logger.\n\n"
                    "- {'[*] [abc123]': [TodoItem(...)]}\n\n"
                    "</todo-state>\n"
                    "## More instructions\n"
                    "Keep the output concise."
                )
            )
        ]
    )

    assert deserializer.instructions == (
        "## Tool instructions\nUse the tools carefully.\n\n"
        "## More instructions\nKeep the output concise."
    )
    assert deserializer.todos == (
        "- [*] [abc123] Inspect the logger.\n\n"
        "- {'[*] [abc123]': [TodoItem(...)]}"
    )

    ordinary = InstructionDeserializer(
        [InstructionPart(content="## Current Todos\n- this is ordinary text")]
    )
    assert ordinary.todos == ""
    assert ordinary.instructions == "## Current Todos\n- this is ordinary text"


def test_instruction_deserializer_preserves_repeated_todo_blocks():
    block = "<todo-state>\n- [ ] inspect\n</todo-state>"
    deserializer = InstructionDeserializer(
        [InstructionPart(content=block), InstructionPart(content=block)]
    )

    assert deserializer.todos == "- [ ] inspect\n\n- [ ] inspect"


def test_model_traffic_logger_uses_pydantic_ai_lifecycle_hooks(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    agent = Agent(TestModel(custom_output_text="answer"), capabilities=[capability])

    result = asyncio.run(agent.run("question"))

    assert result.output == "answer"
    entries = [yml.from_yaml(item) for item in captured]
    assert [entry["event"] for entry in entries] == ["model-request", "model-response"]
    assert entries[0]["messages"] == [{"kind": "user-prompt", "content": "question"}]
    assert entries[1]["messages"] == [{"kind": "text", "content": "answer"}]
