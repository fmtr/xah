from __future__ import annotations

from acp.schema import AgentThoughtChunk
from pydantic_acp.runtime import PydanticAcpAgent
from pydantic_ai import UsageLimits

from xah.server.acp.thinking import ThinkingPromptExecution


class AgentAcp(PydanticAcpAgent):
    """

    ACP agent to fix things that Pydantic AI throws away, like thinking events and usage limits.

    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._prompt_runtime._execution = ThinkingPromptExecution(self._prompt_runtime)

    def _build_run_kwargs(self, **kwargs):
        run_kwargs = super()._build_run_kwargs(**kwargs)
        run_kwargs["usage_limits"] = UsageLimits(request_limit=None)
        return run_kwargs

    async def _record_update(self, session, update):
        """Send thought chunks without storing them in pydantic-acp's transcript.

        pydantic-acp 1.5.1's stored transcript union does not include
        ``AgentThoughtChunk``, although ACP supports it as a live session
        update.  Persisting one through the base implementation raises before
        the update reaches the client.
        """
        if isinstance(update, AgentThoughtChunk):
            if self._client is not None:
                await self._client.session_update(
                    session_id=session.session_id,
                    update=update,
                )
            return
        await super()._record_update(session, update)

    def _restore_default_model(self, agent, session):
        del agent, session # I think stops fallback on model error.
        return False
