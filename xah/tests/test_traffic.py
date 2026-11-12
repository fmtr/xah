import asyncio
import json
from types import SimpleNamespace
from typing import ClassVar

from pydantic_ai import Agent
from pydantic_ai.messages import (
    AgentInstructionSource,
    BinaryContent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    InstructionId,
    InstructionPart,
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolsetInstructionSource,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel
from pydantic_ai.toolsets import CombinedToolset

from corio import yml
from corio.iterator import ilist
from xah.caps.traffic import InstructionDeserializer, ModelTrafficLogger
from xah.harness.base import HarnessAcp
from xah.instructions.base import Instruction
from xah.instructions.registry import Instructions as InstructionRegistry
from xah.toolsets.base.toolset import Toolset
from xah.toolsets.management.toolset import Management
from xah.toolsets.todo.constants import TodoStatus
from xah.toolsets.todo.item import TodoItem
from xah.toolsets.todo.list import TODO_SYSTEM_PROMPT, TodoList


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
    request = ModelRequest(parts=[UserPromptPart('{"task": "synthetic"}')])
    response = ModelResponse(
        parts=[
            ThinkingPart("Processing sample input."),
            ToolCallPart(
                tool_name="write_file",
                args=json.dumps(json.dumps({"path": "sample.txt"})),
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
            "messages": [{"kind": "user-prompt", "content": {"task": "synthetic"}}],
        },
        {
            "agent": "root",
            "event": "model-response",
            "model": "test-model",
            "messages": [
                {"kind": "thinking", "content": "Processing sample input."},
                {
                    "kind": "tool-call",
                    "tool_name": "write_file",
                    "tool_call_id": "call-1",
                    "args": {"path": "sample.txt"},
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


def test_model_traffic_logger_records_feedback_added_before_the_model_call(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    warning = "Context usage is high; compact before continuing."
    request_context = SimpleNamespace(
        messages=[ModelRequest(parts=[UserPromptPart("Synthetic task alpha.")])],
        model=SimpleNamespace(model_name="test-model"),
        model_request_parameters=SimpleNamespace(instruction_parts=[], tool_defs={}),
    )
    ctx = SimpleNamespace(run_id="run-1")

    async def handler(context):
        context.messages = [
            ModelRequest(
                parts=[
                    *context.messages[0].parts,
                    SystemPromptPart(content=warning),
                ]
            )
        ]
        return ModelResponse(parts=[TextPart("Done.")], model_name="test-model")

    asyncio.run(capability.wrap_model_request(ctx, request_context=request_context, handler=handler))

    entries = [yml.from_yaml(item) for item in captured]
    request = next(entry for entry in entries if entry["event"] == "model-request")
    assert any(
        part["kind"] == "system-prompt" and part["content"] == warning
        for part in request["messages"]
    )


def test_model_traffic_logger_logs_compacted_history(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    harness = HarnessAcp.__new__(HarnessAcp)
    harness.__dict__["model_traffic_logger"] = capability
    harness.__dict__["session_usage_reporter"] = SimpleNamespace(report=lambda *_: None)
    compressed = []
    harness.__dict__["deps"] = SimpleNamespace(after_compress=lambda: compressed.append(True))
    context_manager = harness.context_manager
    context_manager.max_tokens = 100_000
    context_manager._resolved_max_tokens = 100_000
    context_manager._summarization_processor.max_input_tokens = 100_000
    summary = "Synthetic summary: preserve state and next action."
    context_manager.request_compact_with_summary(summary)

    old_request = ModelRequest(parts=[UserPromptPart("Synthetic task alpha.")])
    old_response = ModelResponse(parts=[TextPart("Synthetic step one complete.")], model_name="test-model")
    current_request = ModelRequest(parts=[UserPromptPart("Continue synthetic task.")])
    request_context = SimpleNamespace(
        messages=[old_request, old_response, current_request],
        model=SimpleNamespace(model_name="test-model"),
    )

    ctx = SimpleNamespace(
        messages=request_context.messages,
        deps=SimpleNamespace(
            models=SimpleNamespace(
                current=SimpleNamespace(CONTEXT_COMPACTION_THRESHOLD=0.8),
            ),
        ),
    )

    async def run():
        await context_manager.before_model_request(ctx, request_context)

    asyncio.run(run())

    entries = [yml.from_yaml(item) for item in captured]
    compactions = [entry for entry in entries if entry["event"] == "context-compaction"]
    assert len(compactions) == 1
    assert compactions[0]["summary"] == summary
    assert compressed == [True]
    messages = compactions[0]["messages"]
    assert len(messages) == 2
    assert messages[0]["kind"] == "request"
    assert messages[0]["parts"][0]["part_kind"] == "user-prompt"
    assert messages[0]["parts"][0]["content"].endswith(summary)
    assert messages[1]["kind"] == "request"
    assert messages[1]["parts"][0]["part_kind"] == "user-prompt"
    assert messages[1]["parts"][0]["content"] == "Continue synthetic task."


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


def instruction_part(content, source, name=None):
    source_id = AgentInstructionSource() if source == "agent" else ToolsetInstructionSource(source)
    identifier = InstructionId(source_id, name=name)
    return InstructionPart(content=content, id=identifier, name=name, dynamic=True)


def todo_instruction_content(items=None):
    if items is None:
        items = [
            TodoItem(id="abc123", content="Inspect the logger", status=TodoStatus.PENDING),
            TodoItem(id="def456", content="Review the setup", status=TodoStatus.IN_PROGRESS),
        ]
    return TodoList(items=ilist(items)).instructions[0].content


def setup_context(parts, tools=()):
    return SimpleNamespace(
        model_request_parameters=SimpleNamespace(
            instruction_parts=parts,
            tool_defs={name: object() for name in tools},
        ),
    )


def test_model_traffic_logger_logs_duplicate_text_from_distinct_sources(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    todo_content = todo_instruction_content()
    context = setup_context(
        [
            instruction_part("Use clear language.", "agent", "Static"),
            instruction_part("Use clear language.", "agent", "Style"),
            instruction_part("Use file tools carefully.", "Files"),
            instruction_part("Check paths before writing.", "Files"),
            instruction_part(todo_content, "Todo"),
        ],
        tools=("read_todos", "update_todo_status"),
    )

    capability.log_setup(context)
    capability.log_setup(context)

    assert [yml.from_yaml(item) for item in captured] == [
        {
            "agent": "root",
            "event": "setup",
            "instructions": [
                {
                    "id": "agent:Static",
                    "source": "agent",
                    "name": "Static",
                    "content": "Use clear language.",
                },
                {
                    "id": "agent:Style",
                    "source": "agent",
                    "name": "Style",
                    "content": "Use clear language.",
                },
                {
                    "id": "toolset:Files",
                    "source": "toolset:Files",
                    "content": "Use file tools carefully.\n\nCheck paths before writing.",
                },
                {
                    "id": "toolset:Todo",
                    "source": "toolset:Todo",
                    "content": todo_content,
                },
            ],
            "tools": ["read_todos", "update_todo_status"],
        },
    ]


def test_model_traffic_logger_logs_only_changed_instruction_and_removals(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    static = instruction_part("Stable guidance.", "agent", "Static")
    time_one = instruction_part("12:01 PM", "agent", "Time")
    optional = instruction_part("Optional guidance.", "agent", "Optional")
    toolset = instruction_part("Use file tools carefully.", "Files")

    capability.log_setup(setup_context([static, time_one, optional, toolset]))
    capability.log_setup(setup_context([toolset, static, instruction_part("12:02 PM", "agent", "Time")]))

    assert [yml.from_yaml(item) for item in captured] == [
        {
            "agent": "root",
            "event": "setup",
            "instructions": [
                {
                    "id": "agent:Static",
                    "source": "agent",
                    "name": "Static",
                    "content": "Stable guidance.",
                },
                {
                    "id": "agent:Time",
                    "source": "agent",
                    "name": "Time",
                    "content": "12:01 PM",
                },
                {
                    "id": "agent:Optional",
                    "source": "agent",
                    "name": "Optional",
                    "content": "Optional guidance.",
                },
                {
                    "id": "toolset:Files",
                    "source": "toolset:Files",
                    "content": "Use file tools carefully.",
                },
            ],
        },
        {
            "agent": "root",
            "event": "setup",
            "instructions": [
                {
                    "id": "agent:Time",
                    "source": "agent",
                    "name": "Time",
                    "content": "12:02 PM",
                },
            ],
            "removed_instructions": ["agent:Optional"],
        },
    ]


def test_model_traffic_logger_tracks_withdrawn_content_and_ignores_empty_parts(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    part = instruction_part("Temporary guidance.", "agent", "Temporary")
    capability.log_setup(setup_context([InstructionPart(content="", dynamic=True)]))
    capability.log_setup(setup_context([part]))
    capability.log_setup(setup_context([InstructionPart(content="", id=part.id, name=part.name)]))
    capability.log_setup(setup_context([]))

    entries = [yml.from_yaml(item) for item in captured]
    assert entries == [
        {
            "agent": "root",
            "event": "setup",
            "instructions": [
                {
                    "id": "agent:Temporary",
                    "source": "agent",
                    "name": "Temporary",
                    "content": "Temporary guidance.",
                }
            ],
        },
        {
            "agent": "root",
            "event": "setup",
            "instructions": [
                {
                    "id": "agent:Temporary",
                    "source": "agent",
                    "name": "Temporary",
                    "content": "",
                }
            ],
        },
    ]


def test_instruction_deserializer_keeps_todo_text_as_a_source_attributed_part():
    content = todo_instruction_content()
    deserializer = InstructionDeserializer([instruction_part(content, "Todo")])

    assert content == (
        f"{TODO_SYSTEM_PROMPT}\n\n"
        f"- {TodoStatus.PENDING.icon} [abc123] Inspect the logger\n"
        f"- {TodoStatus.IN_PROGRESS.icon} [def456] Review the setup"
    )
    assert deserializer.instructions == {
        "toolset:Todo": {
            "id": "toolset:Todo",
            "source": "toolset:Todo",
            "content": content,
        }
    }


def test_unattributed_instruction_parts_do_not_share_a_null_id():
    deserializer = InstructionDeserializer(
        [InstructionPart(content="first contribution"), InstructionPart(content="second contribution")]
    )

    assert deserializer.instructions == {
        "unattributed:0": {"content": "first contribution"},
        "unattributed:1": {"content": "second contribution"},
    }


def test_todo_changes_are_logged_as_one_toolset_instruction(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    static = instruction_part("Keep the plan current.", "agent", "Static")
    one_todo = todo_instruction_content(
        [TodoItem(id="abc123", content="Inspect the logger", status=TodoStatus.PENDING)]
    )
    completed_todo = todo_instruction_content(
        [TodoItem(id="abc123", content="Inspect the logger", status=TodoStatus.COMPLETED)]
    )

    capability.log_setup(setup_context([static, instruction_part(one_todo, "Todo")]))
    capability.log_setup(setup_context([static, instruction_part(completed_todo, "Todo")]))

    entries = [yml.from_yaml(item) for item in captured]
    assert entries[1] == {
        "agent": "root",
        "event": "setup",
        "instructions": [
            {
                "id": "toolset:Todo",
                "source": "toolset:Todo",
                "content": completed_todo,
            }
        ],
    }


def test_instruction_registry_names_and_independently_resolves_harness_instructions(monkeypatch):
    class First(Instruction):
        async def run(self):
            return "Repeated guidance."

    class Second(Instruction):
        async def run(self):
            return ["Repeated guidance.", "A second passage from this source."]

    class Time(Instruction):
        async def run(self):
            return self.ctx.deps.time

    class Optional(Instruction):
        async def run(self):
            return "Optional guidance." if self.ctx.deps.include_optional else ""

    class HarnessType:
        Instructions = [First, Second, Time, Optional]

    capability, captured = captured_logger(monkeypatch)
    agent = Agent(
        TestModel(custom_output_text="answer"),
        deps_type=SimpleNamespace,
        capabilities=[capability],
    )
    InstructionRegistry.register(agent, HarnessType)

    async def run_twice():
        await agent.run(
            "question",
            deps=SimpleNamespace(time="12:01 PM", include_optional=True),
        )
        await agent.run(
            "question",
            deps=SimpleNamespace(time="12:02 PM", include_optional=False),
        )

    asyncio.run(run_twice())

    setups = [
        yml.from_yaml(item)
        for item in captured
        if yml.from_yaml(item)["event"] == "setup"
    ]
    assert setups == [
        {
            "agent": "root",
            "event": "setup",
            "instructions": [
                {
                    "id": "agent:First",
                    "source": "agent",
                    "name": "First",
                    "content": "Repeated guidance.",
                },
                {
                    "id": "agent:Second",
                    "source": "agent",
                    "name": "Second",
                    "content": "Repeated guidance.\n\nA second passage from this source.",
                },
                {
                    "id": "agent:Time",
                    "source": "agent",
                    "name": "Time",
                    "content": "12:01 PM",
                },
                {
                    "id": "agent:Optional",
                    "source": "agent",
                    "name": "Optional",
                    "content": "Optional guidance.",
                },
            ],
        },
        {
            "agent": "root",
            "event": "setup",
            "instructions": [
                {
                    "id": "agent:Time",
                    "source": "agent",
                    "name": "Time",
                    "content": "12:02 PM",
                }
            ],
            "removed_instructions": ["agent:Optional"],
        },
    ]


def test_model_traffic_logger_observes_pydantic_toolset_instructions(monkeypatch):
    class GuidanceToolset(Toolset):
        call_count: ClassVar[int] = 0

        async def get_instructions(self, ctx):
            del ctx
            type(self).call_count += 1
            return [
                InstructionPart(content="Use file tools carefully.", dynamic=True),
                InstructionPart(content="Check paths before writing.", dynamic=True),
            ]

    GuidanceToolset.call_count = 0
    capability, captured = captured_logger(monkeypatch)
    agent = Agent(
        TestModel(custom_output_text="answer"),
        deps_type=SimpleNamespace,
        capabilities=[capability],
        toolsets=[CombinedToolset([GuidanceToolset().wrapper])],
    )

    asyncio.run(agent.run("question", deps=SimpleNamespace()))

    setup = next(
        yml.from_yaml(item)
        for item in captured
        if yml.from_yaml(item)["event"] == "setup"
    )
    assert setup["instructions"] == [
        {
            "id": "toolset:GuidanceToolset",
            "source": "toolset:GuidanceToolset",
            "content": "Use file tools carefully.\n\nCheck paths before writing.",
        }
    ]
    assert GuidanceToolset.call_count == 1


def test_model_traffic_logger_uses_pydantic_ai_lifecycle_hooks(monkeypatch):
    capability, captured = captured_logger(monkeypatch)
    agent = Agent(TestModel(custom_output_text="answer"), capabilities=[capability])

    result = asyncio.run(agent.run("question"))

    assert result.output == "answer"
    entries = [yml.from_yaml(item) for item in captured]
    assert [entry["event"] for entry in entries] == ["model-request", "model-response"]
    assert entries[0]["messages"] == [{"kind": "user-prompt", "content": "question"}]
    assert entries[1]["messages"] == [{"kind": "text", "content": "answer"}]
