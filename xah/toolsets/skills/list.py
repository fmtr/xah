from corio import strings
from xah.toolsets.base.tool import Tool


class List(Tool):
    """List available skill names and summaries."""

    async def run(self) -> str:
        from xah.toolsets.skills.load import Load

        load_name = self.toolset.tool_name(Load)
        lines = [skill.text_description for skill in self.toolset.skills]
        self.feedback(f"Summaries only. Use {load_name} to read the full texts.")
        return strings.trim(*lines)
