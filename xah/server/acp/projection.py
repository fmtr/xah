from __future__ import annotations

from dataclasses import replace

from pydantic_acp.projection import (
    _is_output_tool,
    _is_tool_call_part,
    _is_tool_return_part,
    build_tool_progress_update as acp_build_tool_progress_update,
    build_tool_start_update,
)
from pydantic_ai import ModelMessage, ModelResponse, RetryPromptPart
from pydantic_ai.messages import NativeToolReturnPart

from xah.toolsets.base.output import Output
from xah.toolsets.base.toolset import Toolset


def build_tool_progress_update(
    part,
    *,
    classifier,
    cwd,
    known_start,
    projection_map,
    serializer,
    toolsets,
):
    if not _is_tool_return_part(part):
        return acp_build_tool_progress_update(
            part,
            classifier=classifier,
            cwd=cwd,
            known_start=known_start,
            projection_map=projection_map,
            serializer=serializer,
        )

    toolset: Toolset = toolsets.for_tool(part.tool_name)
    if part.tool_call_id not in toolset.outputs.call_id:
        output = Output.from_result(part.content)
        part_with_output = replace(part, content=output)
        return acp_build_tool_progress_update(
            part_with_output,
            classifier=classifier,
            cwd=cwd,
            known_start=known_start,
            projection_map=projection_map,
            serializer=serializer,
        )

    output = toolset.outputs.call_id[part.tool_call_id]
    try:
        part_with_output = replace(part, content=output)
        return acp_build_tool_progress_update(
            part_with_output,
            classifier=classifier,
            cwd=cwd,
            known_start=known_start,
            projection_map=projection_map,
            serializer=serializer,
        )
    finally:
        toolset.outputs.remove(output)


def build_tool_updates(
    messages: list[ModelMessage],
    *,
    classifier,
    cwd=None,
    known_starts=None,
    projection_map,
    serializer,
    toolsets,
):
    known_call_starts = dict(known_starts or {})
    updates = []

    for message in messages:
        if isinstance(message, ModelResponse):
            for part in message.parts:
                if _is_tool_call_part(part):
                    if _is_output_tool(part.tool_name):
                        continue
                    if part.tool_call_id in known_call_starts:
                        continue
                    start_update = build_tool_start_update(
                        part,
                        classifier=classifier,
                        cwd=cwd,
                        projection_map=projection_map,
                    )
                    known_call_starts[part.tool_call_id] = start_update
                    updates.append(start_update)
                    continue
                if isinstance(part, NativeToolReturnPart):
                    if _is_output_tool(part.tool_name):
                        continue
                    updates.append(
                        build_tool_progress_update(
                            part,
                            classifier=classifier,
                            cwd=cwd,
                            known_start=known_call_starts.get(part.tool_call_id),
                            projection_map=projection_map,
                            serializer=serializer,
                            toolsets=toolsets,
                        )
                    )
            continue

        for part in message.parts:
            if _is_tool_return_part(part):
                if _is_output_tool(part.tool_name):
                    continue
                updates.append(
                    build_tool_progress_update(
                        part,
                        classifier=classifier,
                        cwd=cwd,
                        known_start=known_call_starts.get(part.tool_call_id),
                        projection_map=projection_map,
                        serializer=serializer,
                        toolsets=toolsets,
                    )
                )
                continue
            if (
                isinstance(part, RetryPromptPart)
                and part.tool_name is not None
                and not _is_output_tool(part.tool_name)
            ):
                updates.append(
                    build_tool_progress_update(
                        part,
                        classifier=classifier,
                        cwd=cwd,
                        known_start=known_call_starts.get(part.tool_call_id),
                        projection_map=projection_map,
                        serializer=serializer,
                        toolsets=toolsets,
                    )
                )

    return updates
