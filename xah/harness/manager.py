from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from corio.function import cp
from corio.iterator import ilist
from pydantic_ai.toolsets import CombinedToolset

from xah.toolsets.base.toolset import Toolset


@dataclass
class ToolsetsManagerAgent:
    parent: Any

    @cp
    def classes(self) -> Sequence[type[Toolset]]:
        return self.parent.toolsets_classes

    @cp
    def is_managed(self) -> bool:
        return any(toolset_class.IS_MANAGEMENT for toolset_class in self.classes)

    @cp
    def all(self) -> ilist[Toolset]:
        toolsets = []
        for toolset_class in self.classes:
            activated = not self.is_managed or toolset_class.IS_MANAGEMENT
            toolsets.append(
                toolset_class(
                    settings=self.parent.settings,
                    cwd=self.parent.cwd_default,
                    activated=activated,
                )
            )

        return ilist(toolsets)

    @property
    def activated(self) -> ilist[Toolset]:
        return ilist(toolset for toolset in self.all if toolset.activated)

    @property
    def permitted(self) -> ilist[Toolset]:
        return self.activated

    @property
    def agent(self) -> ilist[Toolset]:
        common = self.activated.cls.keys() & self.permitted.cls.keys()
        toolsets = ilist()
        for toolset_class in common:
            toolsets.append(self.activated.cls[toolset_class])
        return toolsets

    @property
    def combined(self) -> CombinedToolset:
        return CombinedToolset(self.agent)


@dataclass
class ToolsetsManager(ToolsetsManagerAgent):
    @property
    def permitted(self) -> ilist[Toolset]:
        from xah.options.base import Policy

        return ilist(
            toolset
            for toolset in self.all
            if toolset.options.cls[Policy].enabled
        )

    @property
    def wrapped(self) -> ilist:
        return ilist(toolset.wrapper for toolset in self.agent)

    @property
    def combined(self) -> CombinedToolset:
        return CombinedToolset(self.wrapped)
