from pydantic_acp import SlashCommandResult

from xah.commands.base import Command


class Test(Command):
    """Run a test command."""

    async def run(self) -> SlashCommandResult:
        return SlashCommandResult(text="Test command.")
