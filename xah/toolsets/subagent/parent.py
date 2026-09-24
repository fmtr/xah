from cached_classproperty import cached_classproperty
from pydantic import Field

from xah.toolsets.base.tool import Tool
from xah.toolsets.base.toolset import Base


class Ask(Tool):
    """Ask the parent agent one clarification question."""

    question: str = Field(description="One clarification question for the parent agent.")

    async def run(self) -> str:
        if self.ctx.deps.ask_user is None:
            return "Error: Cannot ask parent - no communication channel configured."
        return str(await self.ctx.deps.ask_user(self.question, []))


class Parent(Base):
    """Parent-agent question tools."""

    @cached_classproperty
    def TOOLS(cls):
        return [Ask]
