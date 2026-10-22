from random import randint

from pydantic import Field

from xah import Tool


class AgeTool(Tool):
    """Use this tool to provide a randomly generated age for a named user."""
    # (1)!

    # (2)!
    user: str = Field(
        ...,
        description="The name of the user whose age you want to know.",  # (3)!
    )

    async def run(self):
        # (4)!
        age = randint(1, 100)
        return f"{self.user} is {age} years old."
