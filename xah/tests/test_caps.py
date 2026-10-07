import json
from types import SimpleNamespace

from corio import yml
from corio.jsn import to_json
from xah.caps.retry import ToolCallArgsDeserialzer
from xah.constants import HARNESS_FEEDBACK


def test_model_retry_logger_retries_nested_json_string(monkeypatch):
    enqueued = []
    calls = []
    capability = ToolCallArgsDeserialzer(label="root")
    ctx = SimpleNamespace(enqueue=enqueued.append)
    call = SimpleNamespace(tool_name="write_file")
    tool_def = SimpleNamespace(
        parameters_json_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }
    )

    async def handler(args):
        calls.append(args)
        if len(calls) == 1:
            raise ValueError("expected object")
        return json.loads(args)

    async def run():
        return await capability.wrap_tool_validate(
            ctx,
            call=call,
            tool_def=tool_def,
            args='"{\\"path\\": \\"notes.txt\\"}"',
            handler=handler,
        )

    import asyncio

    assert asyncio.run(run()) == {"path": "notes.txt"}
    assert calls == ['"{\\"path\\": \\"notes.txt\\"}"', '{"path": "notes.txt"}']
    assert len(enqueued) == 1
    assert enqueued[0].content.startswith(HARNESS_FEEDBACK)
    assert "pass tool arguments as regular JSON" in enqueued[0].content


def test_model_retry_logger_raises_decoded_args_validation_error():
    capability = ToolCallArgsDeserialzer(label="root")
    enqueued = []
    ctx = SimpleNamespace(enqueue=enqueued.append)
    original_error = ValueError("outer JSON value is a string")
    decoded_error = ValueError("path is required")
    calls = 0

    async def handler(args):
        nonlocal calls
        calls += 1
        raise original_error if calls == 1 else decoded_error

    async def run():
        await capability.wrap_tool_validate(
            ctx,
            call=SimpleNamespace(tool_name="write_file"),
            tool_def=SimpleNamespace(parameters_json_schema={}),
            args='"{}"',
            handler=handler,
        )

    import asyncio
    import pytest

    with pytest.raises(ValueError, match="path is required") as exc_info:
        asyncio.run(run())

    assert exc_info.value is decoded_error
    assert len(enqueued) == 1
    assert enqueued[0].content.startswith(HARNESS_FEEDBACK)
    assert "pass tool arguments as regular JSON" in enqueued[0].content


def test_model_retry_logger_keeps_validation_error_when_args_are_not_nested_json():
    capability = ToolCallArgsDeserialzer(label="root")
    validation_error = ValueError("arguments do not match schema")

    async def handler(args):
        raise validation_error

    async def run():
        await capability.wrap_tool_validate(
            SimpleNamespace(enqueue=lambda message: None),
            call=SimpleNamespace(tool_name="write_file"),
            tool_def=SimpleNamespace(parameters_json_schema={}),
            args='{"path": 42}',
            handler=handler,
        )

    import asyncio
    import pytest

    with pytest.raises(ValueError, match="arguments do not match schema") as exc_info:
        asyncio.run(run())

    assert exc_info.value is validation_error


def test_model_retry_logger_recovers_escaped_array_field():
    capability = ToolCallArgsDeserialzer(label="root")
    enqueued = []
    calls = []
    ctx = SimpleNamespace(enqueue=enqueued.append)
    tool_def = SimpleNamespace(
        parameters_json_schema={
            "type": "object",
            "properties": {"todos": {"type": "array"}},
        }
    )

    async def handler(args):
        calls.append(args)
        if isinstance(args["todos"], str):
            raise ValueError("todos must be an array")
        return args

    import asyncio

    result = asyncio.run(
        capability.wrap_tool_validate(
            ctx,
            call=SimpleNamespace(tool_name="write_todos"),
            tool_def=tool_def,
            args={"todos": '[{"content":"test"}]'},
            handler=handler,
        )
    )

    assert result == {"todos": [{"content": "test"}]}
    assert calls == [
        {"todos": '[{"content":"test"}]'},
        {"todos": [{"content": "test"}]},
    ]
    assert len(enqueued) == 1
    assert enqueued[0].content.startswith(HARNESS_FEEDBACK)
    assert "pass nested array and object arguments as JSON values" in enqueued[0].content


def test_model_retry_logger_does_not_recover_wrong_nested_type():
    capability = ToolCallArgsDeserialzer(label="root")
    validation_error = ValueError("todos must be an array")

    async def handler(args):
        raise validation_error

    async def run():
        await capability.wrap_tool_validate(
            SimpleNamespace(enqueue=lambda message: None),
            call=SimpleNamespace(tool_name="write_todos"),
            tool_def=SimpleNamespace(
                parameters_json_schema={
                    "type": "object",
                    "properties": {"todos": {"type": "array"}},
                }
            ),
            args={"todos": '{"content":"test"}'},
            handler=handler,
        )

    import asyncio
    import pytest

    with pytest.raises(ValueError, match="todos must be an array") as exc_info:
        asyncio.run(run())

    assert exc_info.value is validation_error


def test_model_retry_logger_intercepts_tool_schema_errors(monkeypatch):
    captured = []
    enqueued = []
    capability = ToolCallArgsDeserialzer(label="root")
    error = ValueError("invalid integer")
    ctx = SimpleNamespace(retry=2, max_retries=20, enqueue=enqueued.append)
    call = SimpleNamespace(tool_name="write_file", args='{"content": 42}')
    tool_def = SimpleNamespace(
        parameters_json_schema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
        }
    )

    monkeypatch.setattr("xah.caps.retry.logs.sanitize", lambda value: value)
    monkeypatch.setattr("xah.caps.retry.logger.info", captured.append)

    async def run():
        await capability.on_tool_validate_error(
            ctx,
            call=call,
            tool_def=tool_def,
            args={"content": 42},
            error=error,
        )

    import asyncio
    import pytest

    with pytest.raises(ValueError, match="invalid integer"):
        asyncio.run(run())

    assert yml.from_yaml(captured[0]) == {
        "agent": "root",
        "part_kind": "model-retry",
        "retry_kind": "tool-schema",
        "retry": 2,
        "max_retries": 20,
        "error": "invalid integer",
        "tool_name": "write_file",
    }
    assert len(enqueued) == 1
    assert enqueued[0].content.startswith(HARNESS_FEEDBACK)
    assert "Remember the tool definition" in enqueued[0].content
    assert to_json(tool_def.parameters_json_schema) in enqueued[0].content


def test_model_retry_logger_intercepts_output_schema_errors(monkeypatch):
    captured = []
    capability = ToolCallArgsDeserialzer(label="sub")
    error = ValueError("missing field")
    ctx = SimpleNamespace(retry=1, max_retries=20)

    monkeypatch.setattr("xah.caps.retry.logs.sanitize", lambda value: value)
    monkeypatch.setattr("xah.caps.retry.logger.info", captured.append)

    async def run():
        await capability.on_output_validate_error(
            ctx,
            output_context=object(),
            output={},
            error=error,
        )

    import asyncio
    import pytest

    with pytest.raises(ValueError, match="missing field"):
        asyncio.run(run())

    assert yml.from_yaml(captured[0]) == {
        "agent": "sub",
        "part_kind": "model-retry",
        "retry_kind": "output-schema",
        "retry": 1,
        "max_retries": 20,
        "error": "missing field",
    }
