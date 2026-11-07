from acp.schema import ContentToolCallContent, TextContentBlock

from corio import strings


class InputOutputBase:
    @staticmethod
    def content_block(text: str) -> ContentToolCallContent:
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
