from pydantic import Field

from xah.toolsets.web.base import WebTool


class Research(WebTool):
    """Research a subject and save the resulting material to the knowledgebase."""

    input: str = Field(description="Research question or subject.")

    async def run(self) -> dict:
        return {
            "status": "not_implemented",
            "input": self.input,
        }
