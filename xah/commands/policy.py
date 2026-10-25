from pydantic_acp import SlashCommandResult

from xah.commands.base import Command
from xah.options import base as options


class Policy(Command):
    """Inspect or set a toolset access policy."""

    name: str | None = None
    value: options.Policies | None = None

    async def run(self) -> SlashCommandResult:
        result = await self.run_subs()
        if result.ran:
            return result.result

        toolsets = self.deps.toolsets.all
        if self.name is not None and self.value is not None:
            toolset = toolsets.name[self.name]
            policy = toolset.options.cls[options.Policy]
            policy.current_value = self.value
            return SlashCommandResult(
                text=f"Set {self.name} policy to {self.value}."
            )

        if self.name:
            toolset = toolsets.name[self.name]
            policy = toolset.options.cls[options.Policy]
            return SlashCommandResult(
                text=f"{self.name}: {policy.value}"
            )

        policies = [
            f"{toolset.name}: {toolset.options.cls[options.Policy].value}"
            for toolset in toolsets
        ]
        return SlashCommandResult(text="\n".join(policies))
