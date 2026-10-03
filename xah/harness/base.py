from __future__ import annotations

import asyncio
from functools import cached_property
from typing import Any, Generic, Self, Sequence, TypeVar, cast

from acpremote import serve_acp
from cached_classproperty import cached_classproperty
from corio import PackagePaths, Path, strings
from corio.function import ccp
from corio.iterator import dedupe, enlist, ilist, strip_none
from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities import Thinking
from pydantic_acp import (
    AdapterConfig,
    AgentBridgeBuilder,
    FileSessionStore,
    HarnessFileSystemProjectionMap,
)
from pydantic_acp.projection import (
    DefaultToolClassifier,
    FileSystemProjectionMap,
    ProjectionAwareToolClassifier,
)
from pydantic_deep import ContextManagerCapability, StuckLoopDetection

from xah.constants import (
    PROJECTION_BASH_TOOL_NAMES,
    PROJECTION_EDIT_TOOL_NAMES,
    PROJECTION_READ_TOOL_NAMES,
    PROJECTION_SEARCH_TOOL_NAMES,
    PROJECTION_WRITE_TOOL_NAMES,
)
from xah.caps.traffic import ModelTrafficLogger
from xah.class_collections import ClassDeclaration, resolve_class_collection
from xah.harness.deps import HarnessAgentDeps, HarnessDeps
from xah.models import AdapterModel, Luna
from xah.obs import logger
from xah.options.path import PathCwd, PathRead, PathWrite
from xah.options.provider import ConfigOptionsProvider
from xah.server.acp.thinking import AgentAcp
from xah.server.acp.usage import UsageReporterRegistry
from xah.toolsets.base.toolset import Toolset as ToolsetBase


AgentDepsT = TypeVar("AgentDepsT", bound=HarnessAgentDeps)
DepsT = TypeVar("DepsT", bound=HarnessDeps)


class HarnessAgent(Generic[AgentDepsT]):
    """A directly usable agent without ACP session or launch machinery."""

    title = "Xah"
    description = "Root/orchestrator agent"
    instructions = "Use the prompt and the skills to complete the task."
    deps_type = cast(type[AgentDepsT], HarnessAgentDeps)
    model_settings = {}
    retries = 20
    stuck_loop_max_repeated = 3

    def __init__(self, *, model, cwd_default: Path, settings):
        self.model = model
        self.cwd_default = cwd_default
        self.settings = settings

    @cached_property
    def name(self):
        return type(self).__name__

    @cached_classproperty
    def TOOLSETS(cls) -> ClassDeclaration[ToolsetBase[AgentDepsT]]:
        return []

    @cached_property
    def toolset_classes(self) -> ilist[type[ToolsetBase[AgentDepsT]]]:
        return resolve_class_collection(type(self), "TOOLSETS", "name")

    @cached_property
    def toolsets(self) -> ilist[ToolsetBase[AgentDepsT]]:
        return ilist(
            toolset_type(settings=self.settings, cwd=self.cwd_default)
            for toolset_type in self.toolset_classes
        )

    @cached_property
    def deps_kwargs(self) -> dict[str, Any]:
        return {}

    @cached_property
    def deps(self) -> AgentDepsT:
        return self.deps_type(
            settings=self.settings,
            cwd_default=self.cwd_default,
            toolsets_classes=self.toolset_classes,
            model=self.model,
            **self.deps_kwargs,
        )

    @cached_property
    def capabilities(self):
        return []

    @cached_property
    def stuck_loop_detection(self):
        return StuckLoopDetection(max_repeated=self.stuck_loop_max_repeated, ignore_tools=set())

    @cached_property
    def model_traffic_logger(self):
        return ModelTrafficLogger(label=self.name)

    @cached_property
    def agent_capabilities(self):
        return strip_none(
            *self.capabilities,
            self.stuck_loop_detection,
            self.model_traffic_logger,
        )

    @cached_property
    def agent(self) -> Agent[AgentDepsT, str]:
        agent = Agent[AgentDepsT, str](
            model=self.model,
            deps_type=self.deps_type,
            toolsets=[self.deps_type.get_toolset],
            capabilities=self.agent_capabilities,
            retries=self.retries,
        )
        agent.instructions(self.dynamic_instructions)
        agent.description = self.description
        return agent

    @classmethod
    def agents_md_instructions(cls, ctx: RunContext[AgentDepsT]):
        settings = ctx.deps.settings
        path = (settings.path.agents / settings.path.agents_name).resolve()
        cwd = (
            ctx.deps.options.cls[PathCwd].value
            / settings.path.agents_dir
            / settings.path.agents_name
        ).resolve()
        paths = dedupe([path, cwd])
        texts = [path.read_text() for path in paths if path.exists()]
        return texts

    @classmethod
    def get_paths_instructions(cls, ctx: RunContext[AgentDepsT]) -> str:
        cwd = ctx.deps.options.cls[PathCwd].value
        read = ctx.deps.options.cls[PathRead].value
        write = ctx.deps.options.cls[PathWrite].value
        return strings.trim(
            f"""
            The current working directory/repo is "{cwd}".
            You have read access to "{read}".
            You have write access to "{write}".
            """
        )

    @classmethod
    async def dynamic_instructions(cls, ctx: RunContext[AgentDepsT]) -> str:
        instructions = [
            cls.instructions,
            *cls.agents_md_instructions(ctx),
            cls.get_paths_instructions(ctx),
        ]
        return "\n\n".join(instructions)

    @classmethod
    def from_parent(cls, parent: Harness) -> Self:
        self = cls(
            model=parent.deps.model,
            settings=parent.settings,
            cwd_default=parent.cwd_default,
        )
        from xah.options.base import Policy, FULL

        for option in self.deps.options:
            parent_option = parent.deps.options.name[option.name]
            if isinstance(option, Policy):
                self.deps.set_config_value(option.name, FULL)
                continue
            option.current_value = parent_option.current_value
        return self


class Harness(HarnessAgent[DepsT], Generic[DepsT]):
    """The ACP-backed harness and launchable application entry point."""

    deps_type = HarnessDeps
    thinking_effort = "low"

    def __init__(
        self,
        *,
        session=None,
        bridges: Sequence[Any] = (),
        usage_reporters: UsageReporterRegistry,
    ):
        self.session = session
        self.bridges = tuple(bridges)
        self.usage_reporters = usage_reporters

    @cached_property
    def session_id(self):
        return self.session.session_id

    @cached_classproperty
    def TOOLSETS(cls) -> ClassDeclaration[ToolsetBase[HarnessDeps]]:
        from xah.toolsets.context.toolset import Context
        from xah.toolsets.fs.toolset import Files
        from xah.toolsets.python.toolset import Python
        from xah.toolsets.shell.toolset import Shell
        from xah.toolsets.skills.toolset import Skills
        from xah.toolsets.subagent.toolset import Subagent
        from xah.toolsets.todo.toolset import Todo
        from xah.toolsets.utils.toolset import Utils

        return [Context, Files, Shell, Python, Skills, Todo, Utils]

    @cached_classproperty
    def MODELS(cls) -> list[type[AdapterModel]]:
        return [Luna]

    @cached_property
    def model_classes(self) -> ilist[type[AdapterModel]]:
        return resolve_class_collection(type(self), "MODELS", "name")

    @cached_property
    def models(self) -> ilist[AdapterModel]:
        return ilist(model_type() for model_type in self.model_classes)

    @cached_property
    def cwd_default(self):
        return Path(self.session.cwd)

    @cached_property
    def context_manager(self):
        return ContextManagerCapability(
            include_compact_tool=False,
            on_usage_update=self.session_usage_reporter.report,
        )

    @cached_property
    def session_usage_reporter(self):
        return self.usage_reporters.for_session(self.session.session_id)

    @cached_property
    def deps(self) -> HarnessDeps:
        return self.deps_type(
            settings=self.settings,
            cwd_default=self.cwd_default,
            toolsets_classes=self.toolset_classes,
            models=self.models,
            model=self.models.current.override,
            context_manager=self.context_manager,
        )

    @cached_property
    def thinking(self):
        return Thinking(effort=self.thinking_effort)

    @cached_property
    def stuck_loop_detection(self):
        from xah.toolsets.fs.edit import Edit
        from xah.toolsets.fs.toolset import Files

        return StuckLoopDetection(
            max_repeated=self.stuck_loop_max_repeated,
            ignore_tools={f"{Files.name}-{Edit.local_name}"},
        )

    @cached_property
    def bridge_capabilities(self):
        return AgentBridgeBuilder(
            session=self.session,
            capability_bridges=self.bridges,
        ).build_capabilities()

    @cached_property
    def agent_capabilities(self):
        return strip_none(
            self.thinking,
            self.context_manager,
            *self.capabilities,
            self.stuck_loop_detection,
            self.model_traffic_logger,
            *self.bridge_capabilities,
        )

    @cached_property
    def agent(self) -> Agent[HarnessDeps, str]:
        agent = Agent[HarnessDeps, str](
            model=self.deps.models.current.override,
            deps_type=self.deps_type,
            toolsets=[self.deps_type.get_toolset],
            capabilities=self.agent_capabilities,
            retries=self.retries,
        )
        agent.instructions(self.dynamic_instructions)
        agent.description = self.description
        return agent

    @classmethod
    async def dynamic_instructions(cls, ctx: RunContext[HarnessDeps]) -> str:
        from xah.toolsets.todo.toolset import Todo

        instructions = [
            cls.instructions,
            *cls.agents_md_instructions(ctx),
            cls.get_paths_instructions(ctx),
            ctx.deps.toolsets.name[Todo.name].system_prompt,
        ]
        return "\n\n".join(instructions)

    def restore_session(self):
        for config_id, value in self.session.config_values.items():
            if config_id in self.deps.options.name:
                self.deps.set_config_value(config_id, value)

    @cached_property
    def session_store(self):
        return FileSessionStore(self.settings.path.sessions)

    @cached_property
    def approval_bridge(self):
        from xah.server.acp.server import ApprovalBridgeMetadata

        return ApprovalBridgeMetadata()

    @cached_property
    def projections(self):
        if self.session is None:
            return ilist()

        tools = [
            (toolset, tool_class)
            for toolset in self.deps.toolsets
            for tool_class in toolset.tool_classes
        ]
        projections = [
            (toolset, tool_class, projection)
            for toolset, tool_class in tools
            for projection in strip_none(*enlist(tool_class.projections))
        ]
        projection_maps = []
        for toolset, tool_class, projection in projections:
            if not isinstance(projection, str):
                projection_maps.append(projection)
                continue

            tool_name = toolset.tool_name(tool_class)
            if projection == PROJECTION_BASH_TOOL_NAMES:
                projection_maps.append(FileSystemProjectionMap(
                    bash_tool_names=frozenset({tool_name}), command_arg="shell"
                ))
                continue

            projection_fields = {
                PROJECTION_READ_TOOL_NAMES: frozenset(),
                PROJECTION_WRITE_TOOL_NAMES: frozenset(),
                PROJECTION_EDIT_TOOL_NAMES: frozenset(),
                PROJECTION_SEARCH_TOOL_NAMES: frozenset(),
            }
            projection_fields[projection] = frozenset({tool_name})
            projection_maps.append(HarnessFileSystemProjectionMap(**projection_fields))

        return ilist(projection_maps)

    @cached_property
    def agent_source(self):
        from xah.server.acp.server import SessionAgentSource

        return SessionAgentSource[HarnessDeps](
            harness_type=type(self),
            settings=self.settings,
            usage_reporters=self.usage_reporters,
            capability_bridges=self.bridges,
            projection_maps=self.projections,
        )

    @cached_property
    def config_options_provider(self):
        return ConfigOptionsProvider(self.agent_source)

    @cached_property
    def adapter_config(self):
        return AdapterConfig(
            agent_name=self.name,
            agent_title=self.title,
            approval_bridge=self.approval_bridge,
            capability_bridges=self.bridges,
            config_options_provider=self.config_options_provider,
            available_models=self.models,
            session_store=self.session_store,
            projection_maps=self.projections,
            tool_classifier=ProjectionAwareToolClassifier(
                base_classifier=DefaultToolClassifier(),
                projection_maps=self.projections,
            ),
        )

    @cached_property
    def acp_agent(self):
        return AgentAcp(
            self.agent_source,
            config=self.adapter_config,
            usage_reporters=self.usage_reporters,
        )

    @property
    def url(self) -> str:
        """

        Default URL.

        """
        url = f'http://{self.settings.host}:{self.settings.port}'
        return url

    def agent_factory(self, connection):
        del connection
        harness = type(self)(bridges=self.bridges, usage_reporters=self.usage_reporters)
        return harness.acp_agent

    @ccp
    def paths(self) -> PackagePaths:
        from xah.paths import paths
        return paths

    @ccp
    def Settings(cls):
        from xah.settings import Settings
        Settings=Settings.subclass(paths=cls.paths)
        return Settings

    @cached_property
    def settings(self):
        return self.Settings.instance

    async def serve(self):
        server = await serve_acp(self.agent_factory, host=self.settings.host, port=self.settings.port)
        logger.info(f"Launching {self.name} at {self.url}")
        async with server:
            await server.serve_forever()

    @classmethod
    async def launch_async(cls):
        self = cls(usage_reporters=UsageReporterRegistry())
        await self.serve()

    @classmethod
    def launch(cls):
        return asyncio.run(cls.launch_async())
