from types import SimpleNamespace

import pytest
from pydantic_acp import SlashCommandRequest

from corio import sets
from xah.commands.base import Command, CommandsProvider
from xah.commands.test import Test
from xah.harness.deps import HarnessDeps


def test_command_uses_corio_subcommand_contract():
    assert issubclass(Command, sets.SubCommand)


class Source:
    def get_runtime(self, session):
        return SimpleNamespace(deps=HarnessDeps())


@pytest.mark.asyncio
async def test_commands_provider_advertises_commands():
    provider = CommandsProvider(agent_source=Source(), command_types=[Test])

    commands = await provider.available_commands(None, None)

    assert [command.name for command in commands] == ["test"]


@pytest.mark.asyncio
async def test_commands_provider_runs_command():
    provider = CommandsProvider(agent_source=Source(), command_types=[Test])
    request = SlashCommandRequest(
        name="test",
        argument=None,
        raw_prompt="/test",
        session=object(),
        agent=object(),
    )

    result = await provider.handle_command(request)

    assert "value='test'" in result.text
    assert "count=1" in result.text
    assert "verbose=False" in result.text


@pytest.mark.asyncio
async def test_commands_provider_parses_cli_arguments():
    provider = CommandsProvider(agent_source=Source(), command_types=[Test])
    request = SlashCommandRequest(
        name="test",
        argument='--value "Ada Lovelace" --count 3 --verbose',
        raw_prompt='/test --value "Ada Lovelace" --count 3 --verbose',
        session=object(),
        agent=object(),
    )

    result = await provider.handle_command(request)

    assert "value='Ada Lovelace'" in result.text
    assert "count=3" in result.text
    assert "verbose=True" in result.text


@pytest.mark.asyncio
async def test_commands_provider_runs_subcommand():
    provider = CommandsProvider(agent_source=Source(), command_types=[Test])
    request = SlashCommandRequest(
        name="test",
        argument='sub --value "Nested value"',
        raw_prompt='/test sub --value "Nested value"',
        session=object(),
        agent=object(),
    )

    result = await provider.handle_command(request)

    assert "value='Nested value'" in result.text
