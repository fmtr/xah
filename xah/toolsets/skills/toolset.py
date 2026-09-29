from functools import cached_property

from cached_classproperty import cached_classproperty
from pydantic_deep import SkillsDirectory

from corio import Path
from corio.iterator import ilist
from xah.toolsets.base.toolset import Toolset
from xah.toolsets.skills.skill import Skill


class Skills(Toolset):
    """Skill discovery and loading tools."""

    @cached_classproperty
    def TOOLS(cls):
        from xah.toolsets.skills.list import List
        from xah.toolsets.skills.load import Load

        return [List, Load]

    def __init__(self, settings, cwd: Path):
        self.path = settings.path.skills.resolve()
        self.cwd = (cwd / settings.path.agents_dir / settings.path.skills_dir).resolve()
        super().__init__()

    @cached_property
    def skills(self) -> ilist[Skill]:
        skills_by_id = {}
        for skill_path in (self.path, self.cwd):
            catalog = SkillsDirectory(path=skill_path, max_depth=None)
            for catalog_skill in catalog.get_skills().values():
                skill = Skill(root=skill_path, **catalog_skill.__dict__)
                skills_by_id[skill.id] = skill
        return ilist(skills_by_id.values())
