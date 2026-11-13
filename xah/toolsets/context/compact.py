from corio import strings
from pydantic import Field
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.output import OutputString
from xah.toolsets.base.tool import Kinds, Tool


class Input(InputBase):
    @property
    def title(self):
        return "Compacting conversation"

    summary: str = Field(
        description=strings.trim("""
            Carefully provide a 500–1,000-word continuation summary containing all information
            a fresh agent needs to continue this work effectively. Cover the original request,
            background and motivation, goals and constraints, decisions and reasons, completed
            work and current state, remaining tasks, blockers, assumptions, and next steps.
            Preserve exact references that may be hard to rediscover: URLs, repository and file
            paths, branch and commit IDs, terminal and session IDs, research IDs, search IDs,
            document IDs, task or issue IDs, tool names, commands and results, and relevant
            configuration. Keep identifiers verbatim. Do not omit details because they seem
            obvious in the current thread. This summary replaces older conversation history.
        """),
    )


class Compact(Tool, Input):
    """Replace older conversation history with an agent-written summary."""

    KIND = Kinds.THINK

    async def run(self) -> OutputString:
        self.ctx.deps.context_manager.request_compact_with_summary(self.summary)
        return OutputString(output=self.summary)
