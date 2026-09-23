from functools import cached_property

from cached_classproperty import cached_classproperty
from subagents_pydantic_ai.retry import RetryConfig

from corio.iterator import ilist
from xah.toolsets.base.toolset import Base
from xah.toolsets.subagent.parent import Parent


class Subagent(Base):
    """Subagent delegation tools."""

    @cached_classproperty
    def TOOLS(cls):
        from xah.toolsets.subagent.task import Task

        return ilist([Task])

    @cached_property
    def retry(self):
        return RetryConfig()

    @cached_property
    def ask_parent_toolset(self) -> Parent:
        return Parent()
