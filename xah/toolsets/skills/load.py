from pydantic import Field
from pydantic_ai import ModelRetry

from corio import strings
from corio.iterator import IterDiffer
from xah.toolsets.base.tool import Tool


class Load(Tool):
    """Load the full text for one or more skills."""

    skill_ids: list[str] = Field(description="Full list of relevant skill IDs to load in one call.")

    async def run(self) -> str:
        from xah.toolsets.skills.list import List

        diff = IterDiffer(before=self.toolset.skills.id.keys(), after=self.skill_ids)
        if diff.added:
            valid = strings.join_natural(diff.before)
            invalid = strings.join_natural(diff.added)
            list_name = self.toolset.tool_name(List)
            raise ModelRetry(f"Invalid skill IDs: {invalid}. Choose IDs shown by {list_name}: {valid}.")
        skills = [self.toolset.skills.id[skill_id] for skill_id in self.skill_ids]
        return strings.trim("# Skills\n\nBelow are the skills you selected.", *(skill.text for skill in skills))
