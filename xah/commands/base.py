from __future__ import annotations

import shlex
from collections.abc import Sequence
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO

from acp.schema import AvailableCommand
from pydantic import PrivateAttr, ValidationError
from pydantic_acp import SlashCommandRequest, SlashCommandResult
from pydantic_settings import (
    BaseSettings,
    CliSettingsSource,
    PydanticBaseSettingsSource,
    SettingsError,
)

from corio import sets, strings
from corio.function import ccp, cp
from corio.iterator import ilist
from corio.logs import logger
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
            super().__init__(
                _cli_parse_args=cli_args,
                _cli_exit_on_error=False,
                **data,
            )
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

    @classmethod
    def get_cli_source(
        cls,
        settings_cls: type[BaseSettings],
    ) -> CliSettingsSource:
        return CliSettingsSource(
            settings_cls,
            cli_parse_args=settings_cls.model_config.get("cli_parse_args", False),
            cli_prog_name=f"/{settings_cls.__name__.lower()}",
            cli_exit_on_error=False,
        )

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

    @staticmethod
    def _message_result(message: str) -> SlashCommandResult:
        text = strings.trim("```text", message, "```")
        return SlashCommandResult(text=text)

    async def handle_command(self, request: SlashCommandRequest) -> SlashCommandResult:
        try:
            command_type = self.Commands.command_name[request.name]
        except KeyError:
            available = strings.join_natural(
                (command.command_name for command in self.Commands),
                mask="`/{}`",
            )
            message = strings.trim(f"""
                Unknown slash command `/{request.name}`.
                Available commands: {available}.
            """)
            return self._message_result(message)

        runtime = self.agent_source.get_runtime(request.session)
        output = StringIO()
        try:
            with redirect_stdout(output), redirect_stderr(output):
                command = command_type(
                    request=request,
                    deps=runtime.deps,
                )
        except SystemExit as error:
            message = output.getvalue().strip()
            if error.code == 0:
                help_text = message or f"No help text is available for /{request.name}."
                return self._message_result(help_text)
            if not message:
                message = f"Invalid arguments for /{request.name}. Use --help for usage."
            return self._message_result(message)
        except (SettingsError, ValidationError, ValueError) as error:
            message = output.getvalue().strip() or str(error)
            return self._message_result(
                f"Invalid arguments for /{request.name}: {message}"
            )

        try:
            return await command.run()
        except Exception as error:
            logger.error(
                f"Slash command /{request.name} failed: {error}",
                _exc_info=True,
            )
            return self._message_result(
                f"Slash command /{request.name} failed: {error}"
            )
