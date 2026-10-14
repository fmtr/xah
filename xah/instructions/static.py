from xah.instructions.base import Instruction


class Static(Instruction):
    async def run(self) -> str:
        return self.harness_type.instructions
