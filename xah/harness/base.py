from __future__ import annotations

import asyncio
from functools import cached_property
from typing import Any, Generic, Self, Sequence, TypeVar, cast

from acpremote import TransportOptions, serve_acp
from cached_classproperty import cached_classproperty
from corio import PackagePaths, Path
from corio.function import ccp
from corio.iterator import enlist, ilist, strip_none
from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities import Thinking
from pydantic_acp import (
    AdapterConfig,
    AgentBridgeBuilder,
    FileSessionStore,
    ModelSelectionState,
)
from pydantic_acp.projection import DefaultToolClassifier, ProjectionAwareToolClassifier
from pydantic_deep import ContextManagerCapability, StuckLoopDetection

from xah.caps.traffic import ModelTrafficLogger
from xah.class_collections import classes
from xah.harness.deps import HarnessAgentDeps, HarnessDeps
from xah.models import AdapterModel, Luna
from xah.obs import logger
from xah.options.provider import ConfigOptionsProvider
from xah.server.acp.thinking import AgentAcp
from xah.server.acp.usage import UsageReporterRegistry

from xah.toolsets.base.toolset import Toolset as ToolsetBase
from xah.toolsets.utils.toolset import Utils

AgentDepsT = TypeVar("AgentDepsT", bound=HarnessAgentDeps)
DepsT = TypeVar("DepsT", bound=HarnessDeps)


class HarnessModelsProvider:
    def __init__(self, source, models: ilist[AdapterModel]):
        self.source = source
        self.models = models

    def get_model_state(self, session, agent):
        del agent
        runtime = self.source.get_runtime(session)
        models = runtime.deps.models
        return ModelSelectionState(
            available_models=list(models),
            current_model_id=models.current.model_id,
        )

    def set_model(self, session, agent, model_id):
        runtime = self.source.get_runtime(session)
        models = runtime.deps.models
        model = models.model_id[model_id]
        models.current = model
        runtime.deps.model = model.override
        agent.model = model.override
        return ModelSelectionState(
            available_models=list(models),
            current_model_id=model.model_id,
        )


class HarnessBase(Generic[AgentDepsT]):
    """A directly usable agent without Xah or ACP-specific defaults."""

    NAME=None
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

    @ccp
    def name(cls):
        return cls.NAME or cls.__name__

    @classes
    def Instructions(cls):
        from xah.instructions.agent import Agent
        from xah.instructions.paths import Paths
        from xah.instructions.static import Static

        return [Static, Agent, Paths]

    @classes
    def Toolsets(cls) -> list[type[ToolsetBase[AgentDepsT]]]:
        return []

    @cached_property
    def toolsets(self) -> ilist[ToolsetBase[AgentDepsT]]:
        return ilist(
            toolset_type(settings=self.settings, cwd=self.cwd_default)
            for toolset_type in self.Toolsets
        )

    @cached_property
    def deps_kwargs(self) -> dict[str, Any]:
        return {}

    @cached_property
    def deps(self) -> AgentDepsT:
        return self.deps_type(
            settings=self.settings,
            cwd_default=self.cwd_default,
            toolsets_classes=self.Toolsets,
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
    def output(self):
        return str

    @ccp
    def paths(self):
        return None

    @ccp
    def Settings(cls):
        from xah.settings import Settings

        return Settings

    @cached_property
    def agent(self) -> Agent[AgentDepsT, str]:
        agent = Agent[AgentDepsT, str](
            model=self.model,
            output_type=self.output,
            deps_type=self.deps_type,
            toolsets=[self.deps_type.get_toolset],
            capabilities=self.agent_capabilities,
            retries=self.retries,
        )
        agent.instructions(self.get_instructions)
        agent.description = self.description
        return agent

    @classmethod
    async def get_instructions(cls, ctx: RunContext[AgentDepsT]) -> str:
        instructions = []
        for instruction_type in cls.Instructions:
            instruction = instruction_type(ctx=ctx, harness_type=cls)
            passages = enlist(await instruction.run())
            instructions.extend(passages)

        return "\n\n".join(instructions)

    @classmethod
    def from_parent(cls, parent: HarnessDeps) -> Self:
        self = cls(
            model=parent.model,
            settings=parent.settings,
            cwd_default=parent.cwd_default,
        )
        from xah.options.base import Policy, FULL

        for option in self.deps.options:
            if isinstance(option, Policy):
                self.deps.set_config_value(option.name, FULL)
                continue
            parent_option = parent.options.name.get(option.name)
            if parent_option is None:
                continue
            option.current_value = parent_option.current_value
        return self


class Harness(HarnessBase[AgentDepsT], Generic[AgentDepsT]):
    """A directly usable agent with Xah's default configuration."""

    thinking_effort = "low"

    @ccp
    def TOOLSETS(cls):
        from xah.toolsets.context.toolset import Context as ContextToolset
        from xah.toolsets.fs.toolset import Files as FilesToolset
        from xah.toolsets.kb.toolset import Knowledgebase as KnowledgebaseToolset
        from xah.toolsets.python.toolset import Python as PythonToolset
        from xah.toolsets.subagent.toolset import Subagent as SubagentToolset
        from xah.toolsets.terminal.toolset import Terminals as TerminalsToolset
        from xah.toolsets.shell.toolset import Shell as ShellToolset
        from xah.toolsets.skills.toolset import Skills as SkillsToolset
        from xah.toolsets.todo.toolset import Todo as TodoToolset
        from xah.toolsets.utils.toolset import Utils as UtilsToolset
        from xah.toolsets.web.toolset import Web as WebToolset

        class Catalogue:
            Context = ContextToolset
            Files = FilesToolset
            Knowledgebase = KnowledgebaseToolset
            Python = PythonToolset
            Subagent = SubagentToolset
            Terminals = TerminalsToolset
            Shell = ShellToolset
            Skills = SkillsToolset
            Todo = TodoToolset
            Utils = UtilsToolset
            Web = WebToolset

        return Catalogue

    @classes
    def Toolsets(cls) -> list[type[ToolsetBase[AgentDepsT]]]:
        return [
            cls.TOOLSETS.Context,
            cls.TOOLSETS.Files,
            cls.TOOLSETS.Terminals,
            cls.TOOLSETS.Shell,
            cls.TOOLSETS.Python,
            # cls.TOOLSETS.Web,
            cls.TOOLSETS.Skills,
            cls.TOOLSETS.Todo,
            cls.TOOLSETS.Utils,
        ]

    @ccp
    def Models(cls) -> list[AdapterModel]:
        return [Luna()]

    @cached_property
    def models(self) -> ilist[AdapterModel]:
        return ilist(self.Models)

    @cached_property
    def thinking(self):
        return Thinking(effort=self.thinking_effort)

    @cached_property
    def stuck_loop_detection(self):
        from xah.toolsets.fs.edit import Edit
        from xah.toolsets.fs.toolset import Files
        from xah.toolsets.utils.sleep import Sleep
        from xah.toolsets.utils.toolset import Utils

        return StuckLoopDetection(
            max_repeated=self.stuck_loop_max_repeated,
            ignore_tools={
                Files.tool_name(Edit),
                Utils.tool_name(Sleep),
            },
        )

    @cached_property
    def agent_capabilities(self):
        return strip_none(
            self.thinking,
            *self.capabilities,
            self.stuck_loop_detection,
            self.model_traffic_logger,
        )

    @ccp
    def paths(self) -> PackagePaths:
        from xah.paths import paths

        return paths

    @ccp
    def Settings(cls):
        from xah.settings import Settings as SettingsBase
        parent = next(base for base in cls.__mro__[1:] if hasattr(base, SettingsBase.__name__))
        Settings = parent.Settings
        if cls.paths is parent.paths:
            return Settings

        return Settings.subclass(paths=cls.paths)

    @classmethod
    def launch(cls):
        from xah.harness.base import HarnessAcp

        class HarnessRuntime(cls, HarnessAcp):
            NAME = cls.name

        return HarnessRuntime.launch_sync()


class HarnessAcp(Harness[DepsT], Generic[DepsT]):
    """The ACP-backed harness and launchable application entry point."""

    deps_type = HarnessDeps

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

    @cached_property
    def cwd_default(self):
        return Path(self.session.cwd)

    def after_compress(self, messages, summarized, summary):
        if not summarized:
            return

        self.model_traffic_logger.log_compaction(messages, summarized, summary)
        self.deps.after_compress()

    @cached_property
    def context_manager(self):
        return ContextManagerCapability(
            include_compact_tool=False,
            on_usage_update=self.session_usage_reporter.report,
            on_after_compress=self.after_compress,
        )

    @cached_property
    def session_usage_reporter(self):
        return self.usage_reporters.for_session(self.session.session_id)

    @cached_property
    def deps(self) -> HarnessDeps:
        return self.deps_type(
            settings=self.settings,
            cwd_default=self.cwd_default,
            toolsets_classes=self.Toolsets,
            models=self.models,
            model=self.models.current.override,
            context_manager=self.context_manager,
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
            *super().agent_capabilities,
            self.context_manager,
            *self.bridge_capabilities,
        )

    @cached_property
    def agent(self) -> Agent[HarnessDeps, str]:
        agent = Agent[HarnessDeps, str](
            model=self.deps.models.current.override,
            output_type=self.output,
            deps_type=self.deps_type,
            toolsets=[self.deps_type.get_toolset],
            capabilities=self.agent_capabilities,
            retries=self.retries,
        )
        agent.instructions(self.get_instructions)
        agent.description = self.description
        return agent

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

        return ApprovalBridgeMetadata(enable_persistent_choices=True)

    @cached_property
    def projections(self):

        projections = []
        for toolset_type in self.Toolsets:
            projections.extend(toolset_type.projections)
        return ilist(projections)

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
            models_provider=HarnessModelsProvider(self.agent_source, self.models),
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

    @cached_property
    def settings(self):
        return self.Settings.instance

    async def serve(self):
        server = await serve_acp(
            self.agent_factory,
            host=self.settings.host,
            port=self.settings.port,
            options=TransportOptions(ping_timeout=600.0),
        )
        logger.info(f"Launching {self.name} at {self.url}")
        async with server:
            await server.serve_forever()

    @classmethod
    async def launch_async(cls):
        self = cls(usage_reporters=UsageReporterRegistry())
        await self.serve()

    @classmethod
    def launch_sync(cls):
        return asyncio.run(cls.launch_async())
