from functools import cached_property

from cached_classproperty import cached_classproperty
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_deep.features.periodic_reminder.capability import build_compact_transcript
from pydantic_graph import decision
from typing import ClassVar, Self, Annotated

from xah.constants import PROJECTION_BASH_TOOL_NAMES
from corio import strings, dm
from corio.shell.dsl import arg, shell
from xah.options.base import Select, FULL
from xah.toolsets.base.subprocess import SubprocessRunner
from xah.toolsets.base.tool import ValidationResult


class Bash(SubprocessRunner):
    """Run a bash shell command in the working directory."""

    shell: str = Field(description="Bash source to execute in the working directory.")

    projections = PROJECTION_BASH_TOOL_NAMES

    @cached_classproperty
    def VALIDATORS(cls):
        return [AdversarialApproval]

    @cached_property
    def expression(self):
        return shell.bash(-arg.c + self.shell)


class AdversaryDecision(dm.Base):
    approval: bool = Field(description="Whether the shell command is appropriate for the task and context.")
    comments: str = Field(description="Comments explaining the validation decision.")


class AdversarialApproval(Bash):

    PROMPT: ClassVar[str]=strings.trim("""    
        Does this shell command seem appropriate relative to this task/context?
        
        # Command
        ```
        {shell}
        ```

        # Context
        {transcript}
    """)

    @cached_property
    def transcript(self)->str:
        transcript = build_compact_transcript(self.ctx.messages, 10)
        return transcript

    @cached_property
    def prompt(self):
        prompt= self.PROMPT.format(transcript=self.transcript, shell=self.shell)
        return prompt

    @cached_property
    def agent(self)->Agent:
        agent= Agent(model=self.ctx.model, output_type=AdversaryDecision)
        return agent


    async def get_decision(self)->AdversaryDecision:
        decision= (await self.agent.run(self.prompt)).output
        return decision

    async def validate(self, result: ValidationResult):

        if self.policy.value==FULL:
            return

        decision = await self.get_decision()
        result.approval |= not decision.approval
        if not decision.approval:
            result.messages.append(decision.comments)


