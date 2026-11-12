from collections.abc import Awaitable, Callable
from typing import Any

from corio.iterator import enlist
from pydantic_ai import Agent, RunContext

from xah.instructions.base import Instruction


class Instructions:
    @staticmethod
    async def from_ctx(
        ctx: RunContext[Any],
        harness_type: type,
        instruction_type: type[Instruction],
    ) -> str:
        instruction = instruction_type(ctx=ctx, harness_type=harness_type)
        passages = enlist(await instruction.run())
        return "\n\n".join(passages)

    @classmethod
    def callback(
        cls,
        harness_type: type,
        instruction_type: type[Instruction],
    ) -> Callable[[RunContext[Any]], Awaitable[str]]:
        async def from_context(ctx: RunContext[Any]) -> str:
            return await cls.from_ctx(ctx, harness_type, instruction_type)

        return from_context

    @classmethod
    def register(cls, agent: Agent[Any, Any], harness_type: type) -> None:
        for instruction_type in harness_type.Instructions:
            agent.instructions(
                cls.callback(harness_type, instruction_type),
                name=instruction_type.__name__,
            )
