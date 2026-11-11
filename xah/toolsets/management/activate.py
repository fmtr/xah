from pydantic import Field

from corio import strings
from corio.function import cp
from corio.iterator import IterDiffer, ilist
from xah.class_collections import classes
from xah.options.base import Policy
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.output import Output
from xah.toolsets.base.projection.base import ProjectionContent
from xah.toolsets.base.tool import Kinds, Tool
from xah.toolsets.base.toolset import Toolset


class Input(InputBase):
    ids: list[str] = Field(description="Toolset IDs.")
    reason: str = Field(
        description="A very short reason to justify why the toolset is needed, and why existing tools cannot achieve your goal."
    )

    @cp
    def title(self) -> str:
        ids = strings.join_natural(self.ids, mask="`{}`")
        toolsets = strings.suffix_plural(len(self.ids), "toolset", full=False)
        return f"Activating {toolsets} {ids}"

    @cp
    def content(self) -> list[ProjectionContent]:
        ids = strings.join_natural(self.ids, mask="`{}`")
        return [self.content_block(f"Toolsets: {ids}\nReason: {self.reason}")]


class ActivationOutput(Output):
    toolset_ids: list[str]
    activated: list[str]
    invalid_ids: list[str]
    management_name: str

    @cp
    def differ(self) -> IterDiffer[str]:
        return IterDiffer(before=self.activated, after=self.toolset_ids)

    @cp
    def new(self) -> list[str]:
        return sorted(self.differ.added)

    @cp
    def agent(self) -> str:
        messages = []

        if self.new:
            toolsets = strings.join_natural(self.new, mask=strings.MASK_QUOTE)
            count = strings.suffix_plural(len(self.new), "toolset")
            messages.append(
                strings.Mask("""
                    Activated {count}: {toolsets}.
                """).format(count=count, toolsets=toolsets)
            )

        if self.invalid_ids:
            invalids_text = strings.join_natural(
                self.invalid_ids, mask=strings.MASK_QUOTE
            )
            messages.append(
                strings.Mask("""
                    The following toolset IDs are not available: {invalids_text}.
                    Use IDs from the `{management_name}` instructions.
                """).format(
                    invalids_text=invalids_text,
                    management_name=self.management_name,
                )
            )

        if not messages:
            messages.append("No new toolsets were activated.")

        return strings.trim(*messages)

    @cp
    def content(self) -> list[ProjectionContent]:
        return [self.content_block(self.agent)]


class Activate(Tool, Input):
    """Activate toolsets by ID."""

    KIND = Kinds.SWITCH_MODE

    @classes
    def Validators(cls):
        return [RejectAlreadyActive, ApproveRequestables]

    @cp
    def permitted(self):
        return self.ctx.deps.toolsets.permitted.name

    @cp
    def valids(self) -> set[str]:
        return IterDiffer(before=self.permitted.keys(), after=self.ids).same

    @cp
    def invalids(self) -> set[str]:
        return IterDiffer(before=self.permitted.keys(), after=self.ids).added

    @cp
    def duplicates(self) -> set[str]:
        activated = self.ctx.deps.toolsets.activated.name
        return IterDiffer(before=activated.keys(), after=self.ids).same

    async def run(self) -> ActivationOutput:
        output = ActivationOutput(
            toolset_ids=sorted(self.valids),
            activated=sorted(self.ctx.deps.toolsets.activated.name.keys()),
            invalid_ids=sorted(self.invalids),
            management_name=self.toolset.name,
        )

        permitted = self.permitted
        for toolset_id in output.new:
            toolset = permitted[toolset_id]
            if not toolset.activated:
                self.toolset.toolsets.append(type(toolset))
            toolset.activated = True

        return output


class RejectAlreadyActive(Activate):
    async def validate(self):
        if not self.duplicates:
            return

        names = strings.join_natural(
            sorted(self.duplicates), mask=strings.MASK_QUOTE
        )
        activate_name = self.toolset.get_name(Activate)
        msg = strings.Mask("""
            Already-active toolsets: {names}.
            Do not call `{activate_name}` for them again. They remain enabled and available in context.
            Request only inactive toolsets when needed; never keep re-enabling already-active toolsets.
        """).format(
            names=names,
            activate_name=activate_name,
        )
        self.validation.messages.errors.append(msg)
        self.validation.abort = True


class ApproveRequestables(Activate):
    @cp
    def requesteds(self) -> ilist[Toolset]:
        return ilist(self.permitted[toolset_id] for toolset_id in self.valids)

    @cp
    def requestables(self) -> ilist[Toolset]:
        return ilist(
            toolset
            for toolset in self.requesteds
            if toolset.options.cls[Policy].value == Policy.Policies.REQUESTABLE
        )

    async def validate(self):
        if not self.requestables:
            return

        names = strings.join_natural(
            self.requestables.name.keys(), mask=strings.MASK_QUOTE
        )
        activate_name = self.toolset.get_name(Activate)
        msg = strings.Mask("""
            The following toolsets require approval before `{activate_name}` can activate them: {names}
            Reason given for request: {reason}
        """).format(
            activate_name=activate_name,
            names=names,
            reason=self.reason,
        )
        self.validation.approval = True
        self.validation.messages.approval.append(msg)

    async def after_approval(self):
        for toolset in self.requestables:
            toolset.options.cls[Policy].current_value = Policy.Policies.APPROVAL
        await self.ctx.deps.update_config()
