from dataclasses import dataclass
from pydantic_ai import RunContext

from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.messages import SystemPromptPart
from pydantic_deep import DeepAgentDeps

from corio import logs, strings, yml
from xah.constants import HARNESS_FEEDBACK
from corio.jsn import from_json, to_json
from xah.obs import logger

@dataclass
class ToolCallArgsDeserialzer(AbstractCapability[DeepAgentDeps]):
    """Log schema-validation failures before Pydantic AI retries the model."""

    label: str

    def _enqueue(self, ctx, *messages: str):
        content = strings.trim(HARNESS_FEEDBACK, *messages)
        ctx.enqueue(SystemPromptPart(content=content))

    def _log(self, ctx: RunContext[DeepAgentDeps], *, kind: str, error, tool_name: str | None = None):
        payload = {
            "agent": self.label,
            "part_kind": "model-retry",
            "retry_kind": kind,
            "retry": ctx.retry,
            "max_retries": ctx.max_retries,
            "error": str(error),
        }
        if tool_name is not None:
            payload["tool_name"] = tool_name
        logger.info(logs.sanitize(yml.to_yaml(payload)))

    async def wrap_tool_validate(self, ctx, *, call, tool_def, args, handler):
        try:
            return await handler(args)
        except Exception as validation_error:
            if isinstance(args, dict):
                properties = tool_def.parameters_json_schema.get("properties", {})
                recovered_args = dict(args)
                recovered = False

                for name, value in args.items():
                    expected_type = properties.get(name, {}).get("type")
                    if not isinstance(value, str) or expected_type not in {"array", "object"}:
                        continue

                    try:
                        decoded_value = from_json(value)
                    except (TypeError, ValueError):
                        continue

                    expected_python_type = list if expected_type == "array" else dict
                    if isinstance(decoded_value, expected_python_type):
                        recovered_args[name] = decoded_value
                        recovered = True

                if not recovered:
                    raise validation_error

                self._enqueue(
                    ctx,
                    "In future, pass nested array and object arguments as JSON values, not escaped JSON strings.",
                )
                return await handler(recovered_args)

            if not isinstance(args, str):
                raise

            try:
                decoded_args = from_json(args)
            except (TypeError, ValueError):
                raise validation_error

            # Regular JSON objects have already had their fair validation attempt.
            # Only retry when the outer JSON value was itself an encoded JSON string.
            if not isinstance(decoded_args, str):
                raise validation_error

            self._enqueue(
                ctx,
                "In future, pass tool arguments as regular JSON, not as a nested/escaped JSON string.",
            )
            return await handler(decoded_args)

    async def on_tool_validate_error(self, ctx, *, call, tool_def, args, error):
        self._log(ctx, kind="tool-schema", tool_name=call.tool_name, error=error)
        self._enqueue(
            ctx,
            "Remember the tool definition and make sure the arguments match its schema:",
            to_json(tool_def.parameters_json_schema),
        )
        raise error

    async def on_output_validate_error(self, ctx, *, output_context, output, error):
        self._log(ctx, kind="output-schema", error=error)
        raise error
