from pydantic import Field
from xah.toolsets.base.tool import Tool
from xah.toolsets.base.toolset import Base
from xah.toolsets.subagent.sig import ParentSig


class AskSig(ParentSig):
    question: str = Field(description="One clarification question for the parent agent.")


class Ask(Tool, AskSig):
    """Ask the parent agent one clarification question."""
    async def run(self) -> str:
        if self.ctx.deps.ask_user is None:
            return "Error: Cannot ask parent - no communication channel configured."
        return str(await self.ctx.deps.ask_user(self.question, []))


class Parent(Base):
    """Parent-agent question tools."""
    TOOLS = (Ask,)
