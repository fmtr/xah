from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from corio.function import cp
from corio.iterator import ilist
from corio.tools import Empty
from pydantic_ai.toolsets import CombinedToolset

from xah.toolsets.base.common import ToolsetBase
from xah.toolsets.base.mcp import ToolsetMCP
from xah.toolsets.base.toolset import Toolset


@dataclass
class ToolsetsManagerAgent:
    parent: Any

    @cp
    def classes(self) -> Sequence[type[ToolsetBase]]:
        return self.parent.toolsets_classes

    @cp
    def all(self) -> ilist[ToolsetBase]:
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

    @cp
    def regular(self) -> ilist[Toolset]:
        return ilist(toolset for toolset in self.all if isinstance(toolset, Toolset))

    @cp
    def mcp(self) -> ilist[ToolsetMCP]:
        return ilist(toolset for toolset in self.all if isinstance(toolset, ToolsetMCP))

    @cp
    def is_managed(self) -> bool:
        return any(toolset_class.IS_MANAGEMENT for toolset_class in self.classes)

    @property
    def activated(self) -> ilist[ToolsetBase]:
        return ilist(toolset for toolset in self.all if toolset.activated)

    @property
    def permitted(self) -> ilist[ToolsetBase]:
        from xah.options.base import Policy

        return ilist(
            toolset
            for toolset in self.all
            if toolset.options.cls[Policy].enabled
        )

    @property
    def agent(self) -> ilist[ToolsetBase]:
        permitted_classes = self.permitted.cls.keys()
        return ilist(
            toolset
            for toolset in self.activated
            if type(toolset) in permitted_classes
        )

    @property
    def regular_agent(self) -> ilist[Toolset]:
        return ilist(toolset for toolset in self.agent if isinstance(toolset, Toolset))

    def for_tool(
        self,
        tool_name: str,
        default: Toolset | None | type[Empty] = Empty,
    ) -> Toolset | None:
        for toolset in self.regular_agent:
            if tool_name in toolset.tools:
                return toolset
        if default is not Empty:
            return default
        raise KeyError(tool_name)

    @property
    def combined(self) -> CombinedToolset:
        return CombinedToolset(self.agent)


@dataclass
class ToolsetsManager(ToolsetsManagerAgent):
    @property
    def wrapped(self) -> ilist:
        return ilist(toolset.wrapper for toolset in self.regular_agent)

    @property
    def combined(self) -> CombinedToolset:
        toolsets = [toolset.as_acp_toolset() for toolset in self.agent]
        return CombinedToolset(toolsets)
