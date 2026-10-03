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

    PROJECTIONS = PROJECTION_BASH_TOOL_NAMES

    @cached_classproperty
    def VALIDATORS(cls):
        return [AdversarialApproval]

    @cached_property
    def expression(self):
        return shell.bash(-arg.c + self.shell)


class AdversaryDecision(dm.Base):
    block: bool = Field(description="Whether the shell command should be blocked.")
    reasons: list[str] = Field(
        description="A short list of short sentences, without numbering or formatting, explaining the reasons for the decision."
    )


class AdversarialApproval(Bash):

    PROMPT: ClassVar[str] = strings.trim("""
        Decide whether to block this shell command. You are a security screen for
        signs that the agent attempting to run the command has been compromised.
        You are not performing a code review. Block only when the command itself,
        together with the task and context, indicates malicious, destructive, or
        otherwise unbidden agent behavior.

        Block commands that:
        - Destroy or tamper with data, systems, or repositories without being requested by the task.
        - Exfiltrate secrets, credentials, tokens, private files, or other sensitive data.
        - Install malware, persistence, unauthorized software, or other malicious payloads.
        - Disable or evade security controls, conceal activity, or attempt to bypass the provided tools.
        - Perform other clearly malicious or destructive actions that are unrelated to the user's request.

        Do not block commands that:
        - Are merely inefficient, inelegant, redundant, or not the optimal way to complete the task.
        - Run scripts or programs whose contents are unavailable to the agent or to you; judge the command by the available context, not by speculation.
        - Could be risky in the abstract but are explicitly requested or required by the task.
        - Modify files, run tests, install ordinary dependencies, or use normal system tools as part of the requested work.
        - Fail, produce warnings, or have side effects that are ordinary consequences of legitimate task execution.

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
        result.approval |= decision.block
        if decision.block:
            result.messages+=decision.reasons


