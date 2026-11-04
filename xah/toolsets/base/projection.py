from __future__ import annotations

from enum import StrEnum, auto
from typing import TYPE_CHECKING, Any

from acp.schema import (
    ContentToolCallContent,
    FileEditToolCallContent,
    TextContentBlock,
    ToolCallLocation,
    ToolCallStatus,
)
from pydantic_acp.projection import ToolProjection as AcpToolProjection

from corio import Path, strings
from corio.function import cp

if TYPE_CHECKING:
    from xah.toolsets.base.tool import Signature, Tool
    from xah.toolsets.base.toolset import Toolset


class Status(StrEnum):
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


class Projection:
    def __init__(
        self,
        *,
        tool_cls: type[Tool],
        toolset_cls: type[Toolset],
        raw_input: Any = None,
        cwd: Path | None = None,
        raw_output: Any = None,
        serialized_output: str | None = None,
        status: ToolCallStatus | None = None,
    ):
        self.tool_cls = tool_cls
        self.toolset_cls = toolset_cls
        self.raw_input = raw_input
        self.cwd = cwd
        self.raw_output = raw_output
        self.serialized_output = serialized_output
        self.status = status

    @property
    def tool_name(self) -> str:
        return self.toolset_cls.get_name(self.tool_cls)

    @cp
    def sig(self) -> Signature | None:
        signature_class = self.tool_cls.sig
        if signature_class is None:
            return None
        return signature_class.model_validate(self.raw_input)

    def title(self) -> str:
        return self.tool_name

    def content(self, text: str) -> ContentToolCallContent:
        return ContentToolCallContent(
            type="content",
            content=TextContentBlock(type="text", text=text),
        )

    @staticmethod
    def code_block(text: str, *, language: str | None = None) -> str:
        fence = f"```{language or ''}"
        return f"{fence}\n{text}\n```"

    @staticmethod
    def preview(text: str, *, limit: int) -> str:
        return strings.truncate_mid(text, limit, flatten_text=True)

    @cp
    def output_text(self) -> str:
        if isinstance(self.raw_output, str):
            return self.raw_output
        return self.serialized_output or str(self.raw_output)

    def start(self) -> AcpToolProjection | None:
        return AcpToolProjection(title=self.title())

    def progress(self) -> AcpToolProjection | None:
        return AcpToolProjection(title=self.title(), status=self.status)


class FileProjection(Projection):
    @cp
    def path(self) -> str:
        return str(self.sig.path)

    @cp
    def locations(self) -> list[ToolCallLocation]:
        return [ToolCallLocation(path=self.path)]


class FileEditProjection(FileProjection):
    @cp
    def old_text(self) -> str:
        path = Path(self.path)
        if not path.is_absolute() and self.cwd is not None:
            path = self.cwd / path
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")

    @cp
    def new_text(self) -> str:
        return self.sig.content

    def start(self) -> AcpToolProjection:
        return AcpToolProjection(
            content=[FileEditToolCallContent(
                type="diff",
                path=self.path,
                old_text=self.old_text,
                new_text=self.new_text,
            )],
            locations=self.locations,
        )

    def progress(self) -> AcpToolProjection | None:
        if self.status != Status.COMPLETED:
            return None
        return self.start()


class NoFileProjection(Projection):
    def start(self) -> None:
        return None

    def progress(self) -> None:
        return None
