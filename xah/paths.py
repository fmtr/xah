from functools import cached_property

from corio import Path
from corio.paths import PackagePaths


class PackagePaths(PackagePaths):

    @cached_property
    def home(self):
        return Path("~/.agents")

    @cached_property
    def prompts(self):
        return self.path / 'prompts'

    @cached_property
    def skills(self):
        return self.repo / 'skills'

paths = PackagePaths()
