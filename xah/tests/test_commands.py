from types import SimpleNamespace

import pytest
from pydantic_acp import SlashCommandRequest, SlashCommandResult

from corio import sets
from xah.commands.base import Command, CommandsProvider
from xah.commands.policy import Policy
from xah.commands.test import Test as SlashTestCommand
from xah.harness.deps import HarnessDeps


def test_command_uses_corio_subcommand_contract():
    assert issubclass(Command, sets.SubCommand)


class Source:
    def get_runtime(self, session):
        return SimpleNamespace(deps=HarnessDeps())


class CrashProbe(Command):
    async def run(self) -> SlashCommandResult:
        raise RuntimeError("synthetic slash-handler failure")


@pytest.mark.asyncio
async def test_commands_provider_advertises_commands():
    provider = CommandsProvider(agent_source=Source(), command_types=[SlashTestCommand])

    commands = await provider.available_commands(None, None)

    assert [command.name for command in commands] == ["test"]


@pytest.mark.asyncio
async def test_commands_provider_runs_command():
    provider = CommandsProvider(agent_source=Source(), command_types=[SlashTestCommand])
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
    provider = CommandsProvider(agent_source=Source(), command_types=[SlashTestCommand])
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
    provider = CommandsProvider(agent_source=Source(), command_types=[SlashTestCommand])
    request = SlashCommandRequest(
        name="test",
        argument='sub --value "Nested value"',
        raw_prompt='/test sub --value "Nested value"',
        session=object(),
        agent=object(),
    )

    result = await provider.handle_command(request)

    assert "value='Nested value'" in result.text


@pytest.mark.asyncio
async def test_commands_provider_returns_policy_help_text():
    provider = CommandsProvider(agent_source=Source(), command_types=[Policy])
    request = SlashCommandRequest(
        name="policy",
        argument="--help",
        raw_prompt="/policy --help",
        session=object(),
        agent=object(),
    )

    result = await provider.handle_command(request)

    assert result.text.startswith("```text")
    assert result.text.endswith("```")
    assert "usage:" in result.text.lower()
    assert "--name" in result.text
    assert "--value" in result.text


@pytest.mark.asyncio
async def test_commands_provider_returns_invalid_argument_errors():
    provider = CommandsProvider(agent_source=Source(), command_types=[SlashTestCommand])
    request = SlashCommandRequest(
        name="test",
        argument="--count not-a-number",
        raw_prompt="/test --count not-a-number",
        session=object(),
        agent=object(),
    )

    result = await provider.handle_command(request)

    assert result.text.startswith("```text")
    assert result.text.endswith("```")
    assert "count" in result.text.lower()
    assert "not-a-number" in result.text


@pytest.mark.asyncio
async def test_commands_provider_returns_unknown_option_errors():
    provider = CommandsProvider(agent_source=Source(), command_types=[SlashTestCommand])
    request = SlashCommandRequest(
        name="test",
        argument="--unknown-option",
        raw_prompt="/test --unknown-option",
        session=object(),
        agent=object(),
    )

    result = await provider.handle_command(request)

    assert "unknown-option" in result.text
    assert "/test" in result.text


@pytest.mark.asyncio
async def test_commands_provider_returns_unknown_command_errors():
    provider = CommandsProvider(agent_source=Source(), command_types=[SlashTestCommand])
    request = SlashCommandRequest(
        name="missing-command",
        argument=None,
        raw_prompt="/missing-command",
        session=object(),
        agent=object(),
    )

    result = await provider.handle_command(request)

    assert "missing-command" in result.text
    assert "/test" in result.text


@pytest.mark.asyncio
async def test_commands_provider_returns_malformed_quoting_errors():
    provider = CommandsProvider(agent_source=Source(), command_types=[SlashTestCommand])
    request = SlashCommandRequest(
        name="test",
        argument='--value "unterminated',
        raw_prompt='/test --value "unterminated',
        session=object(),
        agent=object(),
    )

    result = await provider.handle_command(request)

    assert "/test" in result.text
    assert "quotation" in result.text.lower()


@pytest.mark.asyncio
async def test_commands_provider_returns_command_failures_instead_of_raising():
    provider = CommandsProvider(agent_source=Source(), command_types=[CrashProbe])
    request = SlashCommandRequest(
        name="crashprobe",
        argument=None,
        raw_prompt="/crashprobe",
        session=object(),
        agent=object(),
    )

    result = await provider.handle_command(request)

    assert result.text.startswith("```text")
    assert result.text.endswith("```")
    assert "crashprobe" in result.text
    assert "synthetic slash-handler failure" in result.text
