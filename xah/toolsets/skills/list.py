from pydantic_ai import ModelRetry

from corio import strings
from corio.iterator import IterDiffer
from xah.toolsets.base.tool import Tool


class List(Tool):
    """List available skill names and summaries."""

    async def run(self) -> str:
        from xah.toolsets.skills.load import Load

        load_name = self.toolset.tool_name(Load)
        diff = IterDiffer(
            before=self.toolset.skills.id.keys(),
            after=self.toolset.history,
        )
        if not diff.removed:
            message = strings.Mask("""
                All available skills have already been read.
            """).format()
            raise ModelRetry(str(message))

        skills = [self.toolset.skills.id[skill_id] for skill_id in sorted(diff.removed)]
        lines = [skill.text_description for skill in skills]
        message = strings.Mask("""
            Summaries only. Use {load_name} to read the full texts.
        """).format(load_name=load_name)
        self.feedback(str(message))
        return strings.trim(*lines)
