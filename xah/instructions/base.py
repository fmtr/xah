from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from xah.harness.base import Harness


class Instruction:
    def __init__(self, *, ctx: Any, harness_type: type[Harness]):
        self.ctx = ctx
        self.harness_type = harness_type

    async def run(self) -> str | list[str]:
        raise NotImplementedError
