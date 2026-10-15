from typing import ClassVar

from corio import dm
from corio.function import ccp


class ResearchHistory(dm.Base):
    """A research collection and the prompts that created it."""

    id: str
    desc: str

    @ccp
    def Prompts(cls):
        class ResearchHistoryPrompts(cls):
            prompts: list[str]

        return ResearchHistoryPrompts


class ApprovalMixin(dm.Base):
    """Metadata shared by fixed collections that may require approval."""

    APPROVAL: ClassVar[bool] = False

    @ccp
    def history(cls) -> ResearchHistory:
        return ResearchHistory(id=cls.name, desc=cls.description)
