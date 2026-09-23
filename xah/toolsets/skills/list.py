from corio import strings
from xah.toolsets.base.tool import Tool
from xah.toolsets.skills.sig import SkillsSig


class List(Tool, SkillsSig):
    """List available skill names and summaries."""
    async def run(self) -> str:
        from xah.toolsets.skills.load import Load
        lines = [skill.text_description for skill in self.toolset.skills]
        return strings.trim(*lines, f"Summaries only. Use {Load.name} to read the full texts.")
