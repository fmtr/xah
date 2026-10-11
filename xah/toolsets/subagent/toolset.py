from functools import cached_property

from cached_classproperty import cached_classproperty
from xah.class_collections import classes
from subagents_pydantic_ai.retry import RetryConfig

from xah.toolsets.base.toolset import Toolset
from xah.toolsets.subagent.parent import Parent


class Subagent(Toolset):
    """Subagent delegation tools."""

    @classes
    def Tools(cls):
        from xah.toolsets.subagent.task import Task

        return [Task]

    @cached_property
    def retry(self):
        return RetryConfig()

    @cached_property
    def ask_parent_toolset(self) -> Parent:
        return Parent()
