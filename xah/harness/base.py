from __future__ import annotations

import asyncio
from functools import cached_property

from acp.schema import SessionConfigSelect
from typing import Any, Generic, Sequence, TypeVar, cast

from acpremote import serve_acp
from corio import Path, strings
from corio.iterator import dedupe, enlist, ilist, strip_none
from pydantic_ai import Agent, RunContext
from pydantic_ai.capabilities import Thinking
from pydantic_ai.toolsets import CombinedToolset
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
from pydantic_deep import StuckLoopDetection

from xah.acp.thinking import AgentAcp
from xah import models
from xah.constants import (
    PROJECTION_BASH_TOOL_NAMES,
    PROJECTION_EDIT_TOOL_NAMES,
    PROJECTION_READ_TOOL_NAMES,
    PROJECTION_SEARCH_TOOL_NAMES,
    PROJECTION_WRITE_TOOL_NAMES,
)
from xah.caps.retry import ToolCallArgsDeserialzer
from xah.caps.traffic import ModelTrafficLogger
from xah.harness.deps import HarnessDeps
from xah.obs import logger
from xah.options.path import PathRead, PathWrite
from xah.options.provider import ConfigOptionsProvider
from xah.toolsets.fs.toolset import Files
from xah.toolsets.base.toolset import Base as ToolsetBase
from xah.toolsets.python.toolset import Python
from xah.toolsets.shell.toolset import Shell
from xah.toolsets.skills.toolset import Skills
from xah.toolsets.subagent.toolset import Subagent
from xah.toolsets.todo.toolset import Todo


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
        settings,
        *,
        session=None,
        parent=None,
        bridges: Sequence[Any] = (),
    ):
        self.settings = settings
        self.session = session
        self.parent = parent
        self.bridges = tuple(bridges)

    @cached_property
    def name(self):
        return type(self).__name__

    @cached_property
    def session_id(self):
        return self.session.session_id

    @cached_property
    def TOOLSETS(self) -> ilist[type[ToolsetBase[DepsT]]]:
        return ilist([
            Files,
            Shell,
            Python,
            Skills,
            Subagent,
            Todo,
        ])

    @cached_property
    def toolsets(self) -> ilist[ToolsetBase[DepsT]]:
        return ilist(
            toolset_type(settings=self.settings, cwd=self.cwd)
            for toolset_type in self.TOOLSETS
        )

    @cached_property
    def options_toolsets(self) -> list[SessionConfigSelect]:
        options = []
        for toolset in self.toolsets:
            options += toolset.options
        return options

    @cached_property
    def options(self) -> list[SessionConfigSelect]:
        options=[
            PathRead.from_cwd(
                name=None,
                cwd=self.cwd,
                description="Directory available to read and execute from.",
            ),
            PathWrite.from_cwd(
                name=None,
                cwd=self.cwd,
                description="Directory available for file changes.",
            ),
        ]
        return options

    @cached_property
    def models(self):
        return ilist(models.models)

    @cached_property
    def deps_kwargs(self) -> dict[str, Any]:
        return {}

    @cached_property
    def cwd(self):
        return Path(self.session.cwd)

    @cached_property
    def deps(self) -> DepsT:
        deps = self.deps_type(
            cwd=self.cwd,
            settings=self.settings,
            toolsets=self.toolsets,
            models=self.models,
            options=ilist(self.options_toolsets+self.options),
            **self.deps_kwargs,
        )
        if self.parent is None:
            deps.subagents["default"] = self.subagent.agent
        return deps

    def set_config_option(self, config_id, value):
        self.deps.options.name[config_id].current_value = value

    def restore_session(self):
        for config_id, value in self.session.config_values.items():
            if config_id in self.deps.options.name:
                self.set_config_option(config_id, value)

    @cached_property
    def subagent(self):
        return type(self)(
            self.settings,
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

        name_edit = Edit.name
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
        return strip_none(
            self.thinking,
            self.stuck_loop_detection,
            self.model_traffic_logger,
            self.model_retry_logger,
            *self.bridge_capabilities,
        )

    @staticmethod
    def get_toolset(ctx: RunContext[DepsT]) -> CombinedToolset[DepsT]:
        return CombinedToolset[DepsT](ctx.deps.approval_toolsets)

    @cached_property
    def agent(self) -> Agent[DepsT, str]:
        agent = Agent[DepsT, str](
            model=self.deps.models.current.override,
            #model_settings=self.model_settings,
            deps_type=self.deps_type,
            toolsets=[self.get_toolset],
            capabilities=self.capabilities,
            retries=self.retries,
        )

        agent.instructions(self.dynamic_instructions)
        agent.description = self.description
        return agent

    @property
    def agents_md_instructions(self):
        path = (self.settings.path.agents / self.settings.path.agents_name).resolve()
        cwd = (self.cwd / self.settings.path.agents_dir / self.settings.path.agents_name).resolve()
        paths = dedupe([path, cwd])
        texts = [path.read_text() for path in paths if path.exists()]
        return texts

    def get_paths_instructions(self, ctx: RunContext[DepsT]) -> str:
        instructions = strings.trim(
            f"""
            The current working directory/repo is "{self.cwd}".
            You have read access to "{ctx.deps.options.cls[PathRead].value}".
            You have write access to "{ctx.deps.options.cls[PathWrite].value}".
            """
        )

        return instructions

    async def dynamic_instructions(self, ctx: RunContext[DepsT]) -> str:
        instructions = [
            self.instructions,
            *self.agents_md_instructions,
            self.get_paths_instructions(ctx),
            ctx.deps.toolsets.name[Todo.name].system_prompt,
        ]

        instructions = '\n\n'.join(instructions)
        return instructions

    @cached_property
    def session_store(self):
        return FileSessionStore(self.settings.path.sessions)

    @cached_property
    def approval_bridge(self):
        from xah.acp.server import ApprovalBridgeMetadata

        return ApprovalBridgeMetadata()

    @cached_property
    def projections(self):
        if self.session is None:
            return ilist()

        projections = []
        for toolset in self.toolsets:
            for tool_class in toolset.tool_classes:
                for projection in enlist(tool_class.projections):
                    if projection is None:
                        continue
                    if isinstance(projection, str):
                        tool_name = toolset.tool_name(tool_class)
                        if projection == PROJECTION_BASH_TOOL_NAMES:
                            projection = FileSystemProjectionMap(
                                bash_tool_names=frozenset({tool_name}),
                                command_arg="shell",
                            )
                        else:
                            projection_fields = {
                                PROJECTION_READ_TOOL_NAMES: frozenset(),
                                PROJECTION_WRITE_TOOL_NAMES: frozenset(),
                                PROJECTION_EDIT_TOOL_NAMES: frozenset(),
                                PROJECTION_SEARCH_TOOL_NAMES: frozenset(),
                            }
                            projection_fields[projection] = frozenset({tool_name})
                            projection = HarnessFileSystemProjectionMap(**projection_fields)
                    projections.append(projection)
        return ilist(projections)

    @cached_property
    def agent_source(self):
        from xah.acp.server import SessionAgentSource

        return SessionAgentSource[DepsT](
            harness_type=type(self),
            settings=self.settings,
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
        return AgentAcp(self.agent_source, config=self.adapter_config)

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
            self.settings,
            bridges=self.bridges,
        )
        return harness.acp_agent

    async def serve(self):
        server = await serve_acp(self.agent_factory, host=self.settings.host, port=self.settings.port)

        url = f'http://{self.settings.host}:{self.settings.port}'
        message = f"Launching {self.name} at {url}"
        logger.info(message)
        async with server:
            await server.serve_forever()

    @classmethod
    async def launch_async(cls, settings):
        self = cls(settings)
        await self.serve()

    @classmethod
    def launch(cls, settings):
        return asyncio.run(cls.launch_async(settings))
