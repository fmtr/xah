from types import SimpleNamespace

import pytest
from pydantic_acp import SlashCommandRequest

from xah.commands.base import CommandsProvider
from xah.commands.test import Test
from xah.harness.deps import HarnessDeps


class Source:
    def get_runtime(self, session):
        return SimpleNamespace(deps=HarnessDeps())


@pytest.mark.asyncio
async def test_commands_provider_advertises_commands():
    provider = CommandsProvider(agent_source=Source(), command_types=[Test])

    commands = await provider.available_commands(None, None)

    assert commands[0].name == "test"
    assert commands[0].description == "Run a test command."


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

    assert result.text == "Test command."
