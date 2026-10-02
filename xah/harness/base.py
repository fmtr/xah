from __future__ import annotations

import asyncio
from functools import cached_property
from itertools import chain

from cached_classproperty import cached_classproperty
from typing import Any, Generic, Sequence, TypeVar, cast

from acpremote import serve_acp
from corio import Path, strings, PackagePaths
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

from xah.server.acp.thinking import AgentAcp
from xah.server.acp.usage import UsageReporter, UsageReporterRegistry
from xah.models import AdapterModel, Luna
from xah.constants import (
    PROJECTION_BASH_TOOL_NAMES,
    PROJECTION_EDIT_TOOL_NAMES,
    PROJECTION_READ_TOOL_NAMES,
    PROJECTION_SEARCH_TOOL_NAMES,
    PROJECTION_WRITE_TOOL_NAMES,
)
from xah.caps.retry import ToolCallArgsDeserialzer
from xah.caps.traffic import ModelTrafficLogger
from xah.class_collections import ClassDeclaration, resolve_class_collection
from xah.harness.deps import HarnessDeps
from xah.obs import logger
from xah.options.path import PathCwd, PathRead, PathWrite
from xah.options.provider import ConfigOptionsProvider
from xah.toolsets.fs.toolset import Files
from xah.toolsets.base.toolset import Toolset as ToolsetBase
from xah.toolsets.context.toolset import Context
from xah.toolsets.python.toolset import Python
from xah.toolsets.shell.toolset import Shell
from xah.toolsets.skills.toolset import Skills
from xah.toolsets.subagent.toolset import Subagent
from xah.toolsets.todo.toolset import Todo
from xah.toolsets.utils.toolset import Utils


DepsT = TypeVar("DepsT", bound=HarnessDeps)


class HarnessBase(Generic[DepsT]):
    title = "Xah"
    description = "Root/orchestrator agent"
    instructions = "Use the prompt and the skills to complete the task."

    deps_type = cast(type[DepsT], HarnessDeps)
    model_settings = {}
    retries = 20
    thinking_effort = "low"
    stuck_loop_max_repeated = 3

    def __init__(
        self,
        *,
        session=None,
        parent=None,
        bridges: Sequence[Any] = (),
        usage_reporters: UsageReporterRegistry | None = None,
    ):
        self.session = session
        self.parent = parent
        self.bridges = tuple(bridges)
        self.usage_reporters = usage_reporters or UsageReporterRegistry()

    @cached_property
    def name(self):
        return type(self).__name__

    @cached_property
    def session_id(self):
        return self.session.session_id

    @cached_classproperty
    def TOOLSETS(cls) -> ClassDeclaration[ToolsetBase[DepsT]]:
        return [Context, Files, Shell, Python, Skills, Subagent, Todo, Utils]

    @cached_classproperty
    def MODELS(cls) -> list[type[AdapterModel]]:
        return [Luna]

    @cached_property
    def toolset_classes(self) -> ilist[type[ToolsetBase[DepsT]]]:
        return resolve_class_collection(type(self), "TOOLSETS", "name")

    @cached_property
    def model_classes(self) -> ilist[type[AdapterModel]]:
        return resolve_class_collection(type(self), "MODELS", "name")

    @cached_property
    def models(self) -> ilist[AdapterModel]:
        return ilist(model_type() for model_type in self.model_classes)

    @cached_property
    def deps_kwargs(self) -> dict[str, Any]:
        return {}

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
        if self.session is None:
            return UsageReporter()
        return self.usage_reporters.for_session(self.session.session_id)

    @cached_property
    def deps(self) -> DepsT:
        deps = self.deps_type(
            settings=self.settings,
            cwd_default=self.cwd_default,
            toolsets_classes=self.toolset_classes,
            models=self.models,
            context_manager=self.context_manager,
            **self.deps_kwargs,
        )
        if self.parent is None:
            deps.subagents["default"] = self.subagent.agent
        return deps

    def restore_session(self):
        for config_id, value in self.session.config_values.items():
            if config_id in self.deps.options.name:
                self.deps.set_config_value(config_id, value)

    @cached_property
    def subagent(self):
        return type(self)(
            session=self.session,
            parent=self,
            bridges=self.bridges,
            **self.subagent_kwargs,
        )

    @cached_property
    def subagent_kwargs(self) -> dict[str, Any]:
        return {}

    @cached_property
    def thinking(self):
        return Thinking(effort=self.thinking_effort)

    @cached_property
    def stuck_loop_detection(self):
        from xah.toolsets.fs.edit import Edit

        name_edit = f"{Files.name}-{Edit.local_name}"
        return StuckLoopDetection(
            max_repeated=self.stuck_loop_max_repeated,
            ignore_tools={name_edit},
        )

    @cached_property
    def model_traffic_logger(self):
        return ModelTrafficLogger(label=self.name)

    @cached_property
    def model_retry_logger(self):
        return ToolCallArgsDeserialzer(label=self.name)

    @cached_property
    def bridge_capabilities(self):
        return AgentBridgeBuilder(
            session=self.session,
            capability_bridges=self.bridges,
        ).build_capabilities()

    @cached_property
    def capabilities(self):
        return []

    @cached_property
    def agent_capabilities(self):
        return strip_none(
            self.thinking,
            self.context_manager,
            *self.capabilities,
            self.stuck_loop_detection,
            self.model_traffic_logger,
            self.model_retry_logger,
            *self.bridge_capabilities,
        )

    @cached_property
    def agent(self) -> Agent[DepsT, str]:
        agent = Agent[DepsT, str](
            model=self.deps.models.current.override,
            #model_settings=self.model_settings,
            deps_type=self.deps_type,
            toolsets=[self.deps_type.get_toolset],
            capabilities=self.agent_capabilities,
            retries=self.retries,
        )

        agent.instructions(self.dynamic_instructions)
        agent.description = self.description
        return agent

    @classmethod
    def agents_md_instructions(cls, ctx: RunContext[DepsT]):
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
    def get_paths_instructions(cls, ctx: RunContext[DepsT]) -> str:
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
    async def dynamic_instructions(cls, ctx: RunContext[DepsT]) -> str:
        instructions = [
            cls.instructions,
            *cls.agents_md_instructions(ctx),
            cls.get_paths_instructions(ctx),
            ctx.deps.toolsets.name[Todo.name].system_prompt,
        ]
        return '\n\n'.join(instructions)

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

        toolsets = list(self.deps.toolsets)
        toolset_tools = [
            [(toolset, tool_class) for tool_class in toolset.tool_classes]
            for toolset in toolsets
        ]
        tools = list(chain.from_iterable(toolset_tools))
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
                projection_maps.append(
                    FileSystemProjectionMap(
                        bash_tool_names=frozenset({tool_name}),
                        command_arg="shell",
                    )
                )
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

        return SessionAgentSource[DepsT](
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
        harness = type(self)(
            bridges=self.bridges,
        )
        return harness.acp_agent

    @ccp
    def paths(self)->PackagePaths:
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

        url = f'http://{self.settings.host}:{self.settings.port}'
        message = f"Launching {self.name} at {url}"
        logger.info(message)
        async with server:
            await server.serve_forever()

    @classmethod
    async def launch_async(cls,):
        self = cls()
        await self.serve()

    @classmethod
    def launch(cls,):
        return asyncio.run(cls.launch_async())
