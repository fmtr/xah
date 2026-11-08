from pathlib import Path
from typing import Any

from acp.schema import (
    ContentToolCallContent,
    FileEditToolCallContent,
    ResourceContentBlock,
    TerminalToolCallContent,
    TextContentBlock,
    ToolCallLocation,
)

from corio import jsn, strings


type ProjectionContent = ContentToolCallContent | FileEditToolCallContent | TerminalToolCallContent


class InputOutputBase:
    @property
    def serialized(self) -> Any:
        return self.model_dump(mode="json")

    @property
    def serialized_text(self) -> str:
        return jsn.to_json(self.serialized)

    def tool_location(
        self,
        path: str | Path,
        *,
        line: int | None = None,
    ) -> ToolCallLocation:
        path = Path(path)
        if not path.is_absolute() and self.request.cwd is not None:
            path = Path(self.request.cwd) / path
        return ToolCallLocation(path=str(path.resolve()), line=line)

    @staticmethod
    def content_block(text: str) -> ContentToolCallContent:
        return ContentToolCallContent(
            type="content",
            content=TextContentBlock(type="text", text=text),
        )

    @staticmethod
    def resource_link_content(
        uri: str,
        *,
        name: str,
        title: str,
    ) -> ContentToolCallContent:
        resource = ResourceContentBlock(
            type="resource_link",
            uri=uri,
            name=name,
            title=title,
        )
        return ContentToolCallContent(type="content", content=resource)

    @staticmethod
    def inline_code(text: str) -> str:
        fence = "`"
        while fence in text:
            fence += "`"
        return f"{fence}{text}{fence}"

    @staticmethod
    def code_block(text: str, *, language: str | None = None) -> str:
        fence = "```"
        while fence in text:
            fence += "`"
        language_label = language or ""
        return f"{fence}{language_label}\n{text}\n{fence}"

    @staticmethod
    def preview(text: str, *, limit: int) -> str:
        return strings.truncate_mid(text, limit, flatten_text=True)
