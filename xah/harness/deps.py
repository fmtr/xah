from __future__ import annotations

from acp.schema import SessionConfigSelect
from functools import cached_property
from typing import Any, Self

from pydantic_acp import AdapterModel
from pydantic_ai import ApprovalRequiredToolset

from dataclasses import dataclass, field
from pydantic_deep import DeepAgentDeps

from corio.iterator import ilist
from xah.toolsets.base.toolset import Toolset as ToolsetBase

@dataclass
class HarnessDeps(DeepAgentDeps):
    settings: Any = None
    toolsets: ilist[ToolsetBase[HarnessDeps]] = field(default_factory=ilist)
    options: ilist[SessionConfigSelect] = field(default_factory=ilist)
    models: ilist[AdapterModel] = field(default_factory=ilist)

    @property
    def active_toolsets(self) -> ilist[ToolsetBase[HarnessDeps]]:
        from xah.options.base import Policy

        return ilist(
            selected for selected in self.toolsets
            if selected.options.cls[Policy].enabled
        )

    @property
    def approval_toolsets(self) -> list[ApprovalRequiredToolset[HarnessDeps]]:
        return [selected.wrapper for selected in self.active_toolsets]

    def clone_for_subagent(self, max_depth: int = 0) -> Self:
        # todo decide if necessary give Harness.from_parent
        return super().clone_for_subagent(max_depth=max_depth)
