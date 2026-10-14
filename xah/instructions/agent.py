from corio.iterator import dedupe

from xah.instructions.base import Instruction
from xah.options.path import PathCwd


class Agent(Instruction):
    async def run(self) -> list[str]:
        settings = self.ctx.deps.settings
        path = (settings.path.agents / settings.path.agents_name).resolve()
        cwd = (
            self.ctx.deps.options.cls[PathCwd].value
            / settings.path.agents_dir
            / settings.path.agents_name
        ).resolve()
        paths = dedupe([path, cwd])
        return [path.read_text() for path in paths if path.exists()]
