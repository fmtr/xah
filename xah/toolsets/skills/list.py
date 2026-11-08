from pydantic_ai import ModelRetry

from corio import dm, strings
from corio.iterator import IterDiffer
from xah.toolsets.base.output import Output
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.tool import Kinds, Tool


class Input(InputBase):
    @property
    def title(self):
        return "Listing available skills"


class SkillSummary(dm.Base):
    id: str
    description: str

    @property
    def text_description(self):
        return strings.trim(f"## {self.id}\n{self.description}")


class SkillsOutput(Output):
    skills: list[SkillSummary]

    @property
    def agent(self) -> str:
        return strings.trim(*(skill.text_description for skill in self.skills))

    @property
    def title(self) -> str:
        skill_ids = strings.join_natural(
            (skill.id for skill in self.skills),
            mask="`{}`",
        )
        return f"Listed skills {skill_ids}"

    @property
    def content(self):
        return [self.content_block(skill.text_description) for skill in self.skills]


class List(Tool, Input):
    """List available skill names and summaries."""

    KIND = Kinds.READ

    async def run(self) -> SkillsOutput:
        from xah.toolsets.skills.load import Load

        load_name = self.toolset.get_name(Load)
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
        message = strings.Mask("""
            Summaries only. Use {load_name} to read the full texts.
        """).format(load_name=load_name)
        self.feedback(str(message))
        return SkillsOutput(
            skills=[
                SkillSummary(id=skill.id, description=skill.description)
                for skill in skills
            ]
        )
