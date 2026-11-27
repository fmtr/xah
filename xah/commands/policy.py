from pydantic_acp import SlashCommandResult
from corio import strings
from pydantic_settings import CliSubCommand

from xah.commands.base import Command
from xah.options import base as options


class Reset(Command):
    """Reset all toolset access policies to their defaults."""

    async def run(self) -> SlashCommandResult:
        for toolset in self.deps.toolsets.all:
            policy = toolset.options.cls[options.Policy]
            policy.current_value = toolset.POLICY

        return SlashCommandResult(text="Reset all toolset policies to their defaults.")


class Policy(Command):
    """Inspect or set a toolset access policy."""

    reset: CliSubCommand[Reset]
    name: str | None = None
    value: options.Policies | None = None

    async def run(self) -> SlashCommandResult:
        if self.reset:
            self.reset._deps = self.deps

        result = await self.run_subs()
        if result.ran:
            return result.result

        toolsets = self.deps.toolsets.all
        if self.name is not None:
            try:
                toolset = toolsets.name[self.name]
            except KeyError:
                available = strings.join_natural(
                    (toolset.name for toolset in toolsets),
                    mask="`{}`",
                )
                message = strings.trim(f"""
                    Unknown toolset `{self.name}`.
                    Available toolsets: {available}.
                """)
                text = strings.trim("```text", message, "```")
                return SlashCommandResult(text=text)

            policy = toolset.options.cls[options.Policy]
            if self.value is not None:
                policy.current_value = self.value
                return SlashCommandResult(
                    text=f"Set {self.name} policy to {self.value}."
                )

            return SlashCommandResult(text=f"{self.name}: {policy.value}")

        policies = [
            f"{toolset.name}: {toolset.options.cls[options.Policy].value}"
            for toolset in toolsets
        ]
        return SlashCommandResult(text=strings.join(policies, sep="\n"))
