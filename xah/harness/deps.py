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
from xah.harness.manager import ToolsetsManager, ToolsetsManagerAgent


@dataclass
class HarnessAgentDeps(DeepAgentDeps):
    settings: Any = field(default_factory=lambda: Settings.instance)
    cwd_default: Path = field(default_factory=Path.cwd)
    toolsets_classes: Sequence[type[ToolsetBase[Self]]] = field(default_factory=tuple)
    model: AdapterModel | None = None
    context_manager: ContextManagerCapability | None = field(default=None, kw_only=True)

    @cached_property
    def toolsets(self) -> ToolsetsManagerAgent:
        return ToolsetsManagerAgent(self)

    def after_compress(self):
        for toolset in self.toolsets.all:
            toolset.after_compress()

    @cached_property
    def options(self):
        from xah.options.path import PathCwd, PathRead, PathWrite

        options = [
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
        ]
        toolset_options = ilist(
            option
            for toolset in self.toolsets.all
            for option in toolset.options
        )
        options.extend(
            toolset_options.name[name]
            for name in sorted(toolset_options.name)
        )
        return ilist(options)

    def set_config_value(self, config_id, value):
        self.options.name[config_id].current_value = value

    @staticmethod
    def get_toolset(ctx):
        return ctx.deps.toolsets.combined


@dataclass
class HarnessDeps(HarnessAgentDeps):
    models: ilist[AdapterModel] = field(default_factory=ilist)

    @cached_property
    def options(self):
        from xah.options.path import PathCwd, PathRead, PathWrite

        options = [
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
        ]
        toolset_options = ilist(
            option
            for toolset in self.toolsets.all
            for option in toolset.options
        )
        options.extend(
            toolset_options.name[name]
            for name in sorted(toolset_options.name)
        )
        return ilist(options)

    def set_config_value(self, config_id, value):
        self.options.name[config_id].current_value = value

    @cached_property
    def toolsets(self) -> ToolsetsManager:
        return ToolsetsManager(self)

    @staticmethod
    def get_toolset(ctx):
        return ctx.deps.toolsets.combined

    def clone_for_subagent(self, max_depth: int = 0) -> Self:
        return super().clone_for_subagent(max_depth=max_depth)
