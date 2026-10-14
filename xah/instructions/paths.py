from corio import strings

from xah.instructions.base import Instruction
from xah.options.path import PathCwd, PathRead, PathWrite


class Paths(Instruction):
    async def run(self) -> str:
        cwd = self.ctx.deps.options.cls[PathCwd].value
        read = self.ctx.deps.options.cls[PathRead].value
        write = self.ctx.deps.options.cls[PathWrite].value
        return strings.trim(
            f"""
            The current working directory/repo is "{cwd}".
            You have read access to "{read}".
            You have write access to "{write}".
            """
        )
