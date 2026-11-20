from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from typing import Any, ClassVar

from cached_classproperty import cached_classproperty
from corio import strings
from corio.function import cp
from corio.iterator import ilist
from corio.strings import get_docstring

from xah.options import base as options


@dataclass(kw_only=True)
class ToolsetInfo:
    name: str
    desc: str | None
    tools: list[str]

    @property
    def instruction(self) -> str:
        details = [f"Toolset ID: **{self.name}**", self.desc or ""]
        if self.tools:
            tool_names = strings.trim(*(f"- `{tool}`" for tool in self.tools))
            details.extend(("**Contains**", tool_names))
        return strings.trim(*details)


class ToolsetBase:
    """Shared manager-facing contract for regular and MCP toolsets."""

    ID: ClassVar[str | None] = None
    DESCRIPTION: ClassVar[str | None] = None
    activated: bool = False
    IS_MANAGEMENT: ClassVar[bool] = False
    POLICY: ClassVar[str] = options.Policies.AUTO
    SUPPORTS_REQUESTABLE: ClassVar[bool] = True

    @cached_classproperty
    def name(cls) -> str:
        return cls.ID or cls.__name__

    @cached_classproperty
    def description(cls) -> str | None:
        if cls.DESCRIPTION:
            return cls.DESCRIPTION

        for base in cls.__mro__:
            if base is ToolsetBase:
                return None
            if description := get_docstring(base):
                return description

    @cp
    def info(self) -> ToolsetInfo:
        return ToolsetInfo(
            name=self.name,
            desc=self.description,
            tools=self.tool_names,
        )

    @property
    def tool_names(self) -> list[str]:
        return []

    @cached_property
    def options(self) -> ilist[options.Select]:
        return ilist([
            options.Policy.from_value(
                name=self.name,
                value=self.POLICY,
                description=self.description,
            )
        ])

    @property
    def is_requestable(self) -> bool:
        if not self.SUPPORTS_REQUESTABLE:
            return False

        return self.options.cls[options.Policy].value == options.Policies.REQUESTABLE

    def after_compress(self) -> None:
        pass

    def enable_output_capture(self) -> None:
        pass

    def as_acp_toolset(self) -> Any:
        return self
