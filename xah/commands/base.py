from __future__ import annotations

import shlex
from collections.abc import Sequence

from acp.schema import AvailableCommand
from pydantic import PrivateAttr
from pydantic_acp import SlashCommandRequest
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

from corio import sets
from corio.function import ccp, cp
from corio.iterator import ilist
from corio.strings import get_docstring
from xah.harness.deps import HarnessDeps


class Command(sets.BaseCLI, cli_implicit_flags=True):
    _request: SlashCommandRequest = PrivateAttr(default=None)
    _deps: HarnessDeps = PrivateAttr(default=None)

    def __init__(
        self,
        *,
        request: SlashCommandRequest | None = None,
        deps: HarnessDeps | None = None,
        **data,
    ):
        if request is not None:
            cli_args = shlex.split(request.argument or "")
            super().__init__(_cli_parse_args=cli_args, **data)
        else:
            super().__init__(**data)

        self._request = request
        self._deps = deps

    @classmethod
    def get_init_source(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
    ) -> PydanticBaseSettingsSource:
        return init_settings

    @cp
    def request(self) -> SlashCommandRequest:
        return self._request

    @cp
    def deps(self) -> HarnessDeps:
        return self._deps

    @ccp
    def command_name(cls) -> str:
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
            name=cls.command_name,
            description=cls.description or cls.command_name,
        )

    def exit(self, result):
        return result



class CommandsProvider:
    def __init__(self, agent_source, command_types: Sequence[type[Command]]):
        self.agent_source = agent_source
        self.Commands = ilist(command_types)

    async def available_commands(self, session, agent):
        del session, agent
        return [command_type.available_command for command_type in self.Commands]

    async def handle_command(self, request: SlashCommandRequest):
        command_type = self.Commands.command_name[request.name]
        runtime = self.agent_source.get_runtime(request.session)
        command = command_type(
            request=request,
            deps=runtime.deps,
        )
        return await command.run()
