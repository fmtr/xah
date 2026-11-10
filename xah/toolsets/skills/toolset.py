from functools import cached_property
from typing import Any

from pydantic_ai import RunContext
from pydantic_ai.messages import InstructionPart
from pydantic_deep import SkillsDirectory

from corio import Path, strings
from corio.iterator import ilist
from xah.class_collections import classes
from xah.toolsets.base.toolset import Toolset
from xah.toolsets.skills.skill import Skill


class Skills(Toolset):
    """Skill discovery and loading tools."""

    @classes
    def Tools(cls):
        from xah.toolsets.skills.load import Load

        return [Load]

    def __init__(self, settings, cwd: Path, activated: bool = True):
        self.path = settings.path.skills.resolve()
        self.cwd = (cwd / settings.path.agents_dir / settings.path.skills_dir).resolve()
        super().__init__(activated=activated)

    @cached_property
    def skills(self) -> ilist[Skill]:
        skills_by_id = {}
        for skill_path in (self.path, self.cwd):
            catalog = SkillsDirectory(path=skill_path, max_depth=None)
            for catalog_skill in catalog.get_skills().values():
                skill = Skill(root=skill_path, **catalog_skill.__dict__)
                skills_by_id[skill.id] = skill
        return ilist(skills_by_id.values())

    async def get_instructions(self, ctx: RunContext[Any]) -> list[InstructionPart]:
        del ctx

        loaded_skills = sorted(
            (skill for skill in self.skills if skill.is_loaded),
            key=lambda skill: skill.id,
        )
        available_skills = sorted(
            (skill for skill in self.skills if not skill.is_loaded),
            key=lambda skill: skill.id,
        )
        instructions = []

        if loaded_skills:
            loaded_text = strings.trim(
                strings.Mask("""
                    ## Loaded Skills

                    Below are the texts of the skills you have requested.

                    {skill_texts}
                """).format(
                    skill_texts=strings.trim(*(skill.instruction for skill in loaded_skills))
                )
            )
            instructions.append(InstructionPart(content=loaded_text, dynamic=True))

        if available_skills:
            from xah.toolsets.skills.load import Load

            load_name = self.get_name(Load)
            available_text = strings.trim(
                strings.Mask("""
                    ## Available Skills

                    Summaries only. Use `{load_name}` to read the full texts.

                    {skill_summaries}
                """).format(
                    load_name=load_name,
                    skill_summaries=strings.trim(
                        *(skill.instruction for skill in available_skills)
                    ),
                )
            )
            instructions.append(InstructionPart(content=available_text, dynamic=True))

        return instructions
