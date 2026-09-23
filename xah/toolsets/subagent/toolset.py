from functools import cached_property
from subagents_pydantic_ai.retry import RetryConfig
from xah.toolsets.base.toolset import Base
from xah.toolsets.subagent.parent import Parent
from xah.toolsets.subagent.task import Task


class Subagent(Base):
    """Subagent delegation tools."""
    TOOLS = (Task,)

    @cached_property
    def retry(self):
        return RetryConfig()

    @cached_property
    def ask_parent_toolset(self) -> Parent:
        return Parent()
