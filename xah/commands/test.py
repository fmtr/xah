from pydantic_acp import SlashCommandResult
from pydantic_settings import CliSubCommand

from xah.commands.base import Command


class SubTest(Command):
    """Run a nested test command."""

    value: str = "nested"

    async def run_command(self) -> SlashCommandResult:
        return SlashCommandResult(text=f"Sub-test command: value={self.value!r}.")


class Test(Command):
    """Run a test command."""

    sub: CliSubCommand[SubTest]
    value: str = "test"
    count: int = 1
    verbose: bool = False

    async def run_command(self) -> SlashCommandResult:
        return SlashCommandResult(
            text=(
                f"Test command: value={self.value!r}, "
                f"count={self.count}, verbose={self.verbose}."
            )
        )
