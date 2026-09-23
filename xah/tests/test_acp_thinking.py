import asyncio
from types import SimpleNamespace

from acp import update_agent_thought_text
from acp.schema import AgentThoughtChunk
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, ThinkingPart, ThinkingPartDelta

from xah.acp.thinking import ThinkingPromptExecution
from xah.acp.thinking import AgentAcp


def test_thinking_part_start_becomes_acp_thought_chunk():
    event = PartStartEvent(index=0, part=ThinkingPart(content="Plan first"))

    update = ThinkingPromptExecution.thought_update_from_event(event)

    assert update == update_agent_thought_text("Plan first")
    assert update.session_update == "agent_thought_chunk"
    assert update.content.text == "Plan first"


def test_thinking_part_delta_becomes_acp_thought_chunk():
    event = PartDeltaEvent(index=0, delta=ThinkingPartDelta(content_delta=" then act"))

    update = ThinkingPromptExecution.thought_update_from_event(event)

    assert update.session_update == "agent_thought_chunk"
    assert update.content.text == " then act"


def test_thought_chunks_are_sent_without_transcript_serialization():
    class Client:
        def __init__(self):
            self.updates = []

        async def session_update(self, **kwargs):
            self.updates.append(kwargs)

    class Session:
        session_id = "session-1"
        transcript = []

    agent = object.__new__(AgentAcp)
    agent._client = Client()
    thought = update_agent_thought_text("private reasoning")

    asyncio.run(agent._record_update(Session(), thought))

    assert isinstance(agent._client.updates[0]["update"], AgentThoughtChunk)
    assert not Session.transcript


def test_thought_execution_uses_agent_update_hook():
    class Runtime:
        def __init__(self):
            self._owner = self
            self._config = SimpleNamespace(enable_generic_tool_projection=False)
            self.updates = []

        async def _record_update(self, session, update):
            self.updates.append(update)

        def _text_chunk_from_event(self, event):
            return None

    async def stream():
        yield PartStartEvent(index=0, part=ThinkingPart(content="private reasoning"))

    runtime = Runtime()
    execution = ThinkingPromptExecution(runtime)

    try:
        asyncio.run(
            execution._consume_run_events(
                stream(),
                known_starts={},
                message_id="message-1",
                projection_map=None,
                session=SimpleNamespace(),
                streamed_output=False,
            )
        )
    except RuntimeError as error:
        assert str(error) == "missing_agent_run_result"

    assert len(runtime.updates) == 1
    assert runtime.updates[0] == update_agent_thought_text("private reasoning")
