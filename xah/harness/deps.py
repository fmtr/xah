from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import Any, Self, Sequence

from corio import Path
from corio.iterator import ilist
from pydantic_acp import AdapterModel
from pydantic_deep import ContextManagerCapability, DeepAgentDeps

from xah.settings import Settings
from xah.toolsets.base.toolset import Toolset as ToolsetBase


@dataclass
class HarnessAgentDeps(DeepAgentDeps):
    settings: Any = field(default_factory=lambda: Settings.instance)
    cwd_default: Path = field(default_factory=Path.cwd)
    toolsets_classes: Sequence[type[ToolsetBase[Self]]] = field(default_factory=tuple)
    model: AdapterModel | None = None
    context_manager: ContextManagerCapability | None = field(default=None, kw_only=True)

    @cached_property
    def toolsets(self) -> ilist[ToolsetBase[Self]]:
        return ilist(
            toolset_type(settings=self.settings, cwd=self.cwd_default)
            for toolset_type in self.toolsets_classes
        )

    @cached_property
    def options(self):
        from xah.options.path import PathCwd, PathRead, PathWrite

        options = [
            option
            for toolset in self.toolsets
            for option in toolset.options
        ]
        options.extend([
            PathCwd.from_cwd(
                cwd=self.cwd_default,
                description="Working directory.",
            ),
            PathRead.from_cwd(
                cwd=self.cwd_default,
                description="Directory available to read and execute from.",
            ),
            PathWrite.from_cwd(
                cwd=self.cwd_default,
                description="Directory available for file changes.",
            ),
        ])
        return ilist(options)

    def set_config_value(self, config_id, value):
        self.options.name[config_id].current_value = value

    @staticmethod
    def get_toolset(ctx):
        from pydantic_ai.toolsets import CombinedToolset

        return CombinedToolset(ctx.deps.toolsets)


@dataclass
class HarnessDeps(HarnessAgentDeps):
    models: ilist[AdapterModel] = field(default_factory=ilist)

    @cached_property
    def options(self):
        from xah.options.path import PathCwd, PathRead, PathWrite

        options = [
            option
            for toolset in self.toolsets
            for option in toolset.options
        ]
        options.extend([
            PathCwd.from_cwd(
                cwd=self.cwd_default,
                description="Working directory.",
            ),
            PathRead.from_cwd(
                cwd=self.cwd_default,
                description="Directory available to read and execute from.",
            ),
            PathWrite.from_cwd(
                cwd=self.cwd_default,
                description="Directory available for file changes.",
            ),
        ])
        return ilist(options)

    @property
    def active_toolsets(self) -> ilist[ToolsetBase[Self]]:
        from xah.options.base import Policy

        return ilist(
            selected for selected in self.toolsets
            if selected.options.cls[Policy].enabled
        )

    @property
    def approval_toolsets(self):
        from pydantic_ai import ApprovalRequiredToolset

        return [selected.wrapper for selected in self.active_toolsets]

    def set_config_value(self, config_id, value):
        self.options.name[config_id].current_value = value

    @staticmethod
    def get_toolset(ctx):
        from pydantic_ai.toolsets import CombinedToolset

        return CombinedToolset(ctx.deps.approval_toolsets)

    def clone_for_subagent(self, max_depth: int = 0) -> Self:
        return super().clone_for_subagent(max_depth=max_depth)
