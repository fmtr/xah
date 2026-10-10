from cached_classproperty import cached_classproperty
from pydantic import Field
from pydantic_ai import ModelRetry

from corio import strings
from corio.iterator import IterDiffer
from xah.toolsets.base.tool import Tool, ValidationResult


class Load(Tool):
    """Load the full text for one or more skills."""

    skill_ids: list[str] = Field(description="Full list of relevant skill IDs to load in one call.")

    @cached_classproperty
    def VALIDATORS(cls):
        return [CheckDupes]

    async def run(self) -> str:
        from xah.toolsets.skills.list import List

        diff = IterDiffer(before=self.toolset.skills.id.keys(), after=self.skill_ids)
        if diff.added:
            valid = strings.join_natural(sorted(diff.before))
            invalid = strings.join_natural(sorted(diff.added))
            list_name = self.toolset.tool_name(List)
            message = strings.Mask("""
                Invalid skill IDs: {invalid}.
                Choose IDs shown by {list_name}: {valid}.
            """).format(
                invalid=invalid,
                list_name=list_name,
                valid=valid,
            )
            raise ModelRetry(str(message))
        skills = [self.toolset.skills.id[skill_id] for skill_id in self.skill_ids]
        self.toolset.history |= set(self.skill_ids)
        skill_text = strings.trim(*(skill.text for skill in skills))
        message = strings.Mask("""
            # Skills

            Below are the skills you selected.

            {skill_text}
        """).format(skill_text=skill_text)
        return str(message)


class CheckDupes(Load):
    async def validate(self, result: ValidationResult):
        diff = IterDiffer(before=self.toolset.history, after=self.skill_ids)
        duplicates = diff.same
        if not duplicates:
            return

        duplicate_names = strings.join_natural(sorted(duplicates))
        message = strings.Mask("""
            The skill(s) {skills} have already been loaded.
        """).format(skills=duplicate_names)
        raise ModelRetry(str(message))
