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
            Carefully provide a 500–1,000-word continuation summary containing all information a
            fresh agent needs to continue this work effectively. Organize it with clear headings
            and unordered lists rather than one wall of text.

            ## Session state preserved automatically
            - The harness preserves the current task list, loaded skills, and activated tools
              separately from this summary. Do not repeat their general state here: that would
              duplicate information already supplied to the next agent and could become stale.
            - Mention one of these only when a specific detail materially affects continuation
              and is not evident from the preserved state.

            ## Cover
            - The original request, background and motivation, goals, and constraints.
            - Decisions and the reasons for them; completed work and the current state; remaining
              tasks, blockers, assumptions, and next steps.

            ## Preserve exact references
            - Include references that may be hard to rediscover: URLs; repository and file paths;
              branch and commit IDs; terminal and session IDs; research IDs; search IDs; document
              IDs; task or issue IDs; tool names; commands and results; and relevant configuration.
            - Keep identifiers verbatim. Do not omit details merely because they seem obvious in
              the current thread; this summary replaces older conversation history, so those
              details may otherwise be lost.
        """),
    )


class Compact(Tool, Input):
    """Replace older conversation history with an agent-written summary."""

    KIND = Kinds.THINK

    async def run(self) -> OutputString:
        self.ctx.deps.context_manager.request_compact_with_summary(self.summary)
        return OutputString(output=self.summary)
