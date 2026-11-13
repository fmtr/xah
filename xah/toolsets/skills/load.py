from pydantic import Field

from corio import strings
from corio.function import cp
from corio.iterator import IterDiffer
from xah.class_collections import classes
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.output import Output
from xah.toolsets.base.projection.base import ProjectionContent
from xah.toolsets.base.tool import Kinds, Tool, ValidationAbort


class Input(InputBase):
    skill_ids: list[str] = Field(description="Full list of relevant skill IDs to load in one call.")

    @cp
    def title(self) -> str:
        skill_ids = strings.join_natural(self.skill_ids, mask="`{}`")
        return f"Loading skills {skill_ids}"


class SkillsOutput(Output):
    skill_ids: list[str]
    loaded: list[str]

    @cp
    def differ(self) -> IterDiffer[str]:
        return IterDiffer(before=self.loaded, after=self.skill_ids)

    @cp
    def new(self) -> list[str]:
        return sorted(self.differ.added)

    @cp
    def agent(self) -> str:
        messages = []

        if self.new:
            skill_count = strings.suffix_plural(len(self.new), "skill")
            skill_ids = strings.join_natural(self.new, mask=strings.MASK_QUOTE)
            messages.append(
                strings.Mask("""
                    Loaded {skill_count} into context: {skill_ids}.
                """).format(skill_count=skill_count, skill_ids=skill_ids)
            )

        return strings.trim(*messages)

    @cp
    def content(self) -> list[ProjectionContent]:
        return [self.content_block(self.agent)]


class Load(Tool, Input):
    """Load the full text for one or more skills."""

    KIND = Kinds.READ

    @classes
    def Validators(cls):
        return [ValidSkillIDs]

    @cp
    def loaded(self) -> list[str]:
        return sorted(skill.id for skill in self.toolset.skills if skill.is_loaded)

    @cp
    def known(self) -> list[str]:
        return sorted(skill.id for skill in self.toolset.skills)

    @cp
    def differ(self) -> IterDiffer[str]:
        return IterDiffer(before=self.loaded, after=self.skill_ids)

    @cp
    def new(self) -> list[str]:
        return sorted(self.differ.added)

    @cp
    def dupes(self) -> list[str]:
        return sorted(self.differ.same)

    @cp
    def invalids(self) -> list[str]:
        return sorted(IterDiffer(before=self.known, after=self.skill_ids).added)

    async def run(self) -> SkillsOutput:
        output = SkillsOutput(skill_ids=self.skill_ids, loaded=self.loaded)
        for skill_id in self.new:
            self.toolset.skills.id[skill_id].is_loaded = True
        return output


class ValidSkillIDs(Load):
    async def validate(self):
        if self.invalids:
            invalid_ids = strings.join_natural(self.invalids, mask=strings.MASK_QUOTE)
            known_ids = strings.join_natural(
                self.known,
                mask=strings.MASK_QUOTE,
                if_empty="none",
            )
            message = strings.Mask("""
                Invalid skill IDs: {invalid_ids}.
                Choose IDs shown in the skill instructions: {known_ids}.
            """).format(invalid_ids=invalid_ids, known_ids=known_ids)
            self.validation.messages.errors.append(message)

        if self.dupes:
            dupes = strings.join_natural(self.dupes, mask=strings.MASK_QUOTE)
            skills = strings.suffix_plural(len(self.dupes), "skill", full=False)
            message = strings.Mask("""
                Already-loaded {skills}: {dupes}.
                Do not request them again. They are already in context and do not need to be loaded or read on each turn.
            """).format(skills=skills, dupes=dupes)
            self.validation.messages.errors.append(message)

        if self.invalids or self.dupes:
            raise ValidationAbort()
