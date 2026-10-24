from __future__ import annotations

from collections.abc import Sequence

from acp.schema import AvailableCommand
from pydantic import PrivateAttr
from pydantic_acp import SlashCommandRequest, SlashCommandResult

from corio import dm
from corio.function import ccp, cp
from corio.iterator import ilist
from corio.strings import get_docstring
from xah.harness.deps import HarnessDeps


class Command(dm.Base):
    _request: SlashCommandRequest = PrivateAttr()
    _deps: HarnessDeps = PrivateAttr()

    def __init__(self, *, request: SlashCommandRequest, deps: HarnessDeps, **data):
        super().__init__(**data)
        self._request = request
        self._deps = deps

    @cp
    def request(self) -> SlashCommandRequest:
        return self._request

    @cp
    def deps(self) -> HarnessDeps:
        return self._deps

    @ccp
    def name(cls) -> str:
        return cls.__name__.lower()

    @ccp
    def description(cls) -> str | None:
        for base in cls.__mro__:
            if description := get_docstring(base):
                return description
            if base is Command:
                return None
        return None

    @ccp
    def available_command(cls) -> AvailableCommand:
        return AvailableCommand(
            name=cls.name,
            description=cls.description or cls.name,
        )

    async def run(self) -> SlashCommandResult:
        raise NotImplementedError


class CommandsProvider:
    def __init__(self, agent_source, command_types: Sequence[type[Command]]):
        self.agent_source = agent_source
        self.Commands = ilist(command_types)

    async def available_commands(self, session, agent):
        del session, agent
        return [command_type.available_command for command_type in self.Commands]

    async def handle_command(self, request: SlashCommandRequest):
        command_type = self.Commands.name[request.name]
        runtime = self.agent_source.get_runtime(request.session)
        command = command_type(
            request=request,
            deps=runtime.deps,
        )
        return await command.run()
