from pydantic import Field
from pydantic_ai import ModelRetry
from corio import strings
from corio.iterator import IterDiffer
from xah.toolsets.base.tool import Tool
from xah.toolsets.skills.sig import SkillsSig


class LoadSig(SkillsSig):
    skill_ids: list[str] = Field(description="Full list of relevant skill IDs to load in one call.")


class Load(Tool, LoadSig):
    """Load the full text for one or more skills."""
    async def run(self) -> str:
        from xah.toolsets.skills.list import List
        diff = IterDiffer(before=self.toolset.skills.id.keys(), after=self.skill_ids)
        if diff.added:
            valid = strings.join_natural(diff.before)
            invalid = strings.join_natural(diff.added)
            raise ModelRetry(f"Invalid skill IDs: {invalid}. Choose IDs shown by {List.name}: {valid}.")
        skills = [self.toolset.skills.id[skill_id] for skill_id in self.skill_ids]
        return strings.trim("# Skills\n\nBelow are the skills you selected.", *(skill.text for skill in skills))
