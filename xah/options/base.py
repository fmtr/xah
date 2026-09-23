from typing import Any, ClassVar

from acp.schema import SessionConfigOptionSelect, SessionConfigSelectOption


DISABLED = "disabled"
APPROVAL = "approval"
FULL = "full"


class Select(SessionConfigOptionSelect):
    @property
    def value(self) -> str:
        return self.current_value

    @property
    def enabled(self) -> bool:
        return self.value != DISABLED

    @property
    def approval(self) -> bool:
        return self.current_value != FULL

    @classmethod
    def get_name(cls, name: str | None = None) -> str:
        if name is None:
            return cls.__name__

        return f"{name}/{cls.__name__}"

    @classmethod
    def from_values(
        cls,
        name: str | None = None,
        *,
        values: list[str],
        value: str,
        description: str | None,
        category: str,
        **fields: Any,
    ):
        name = cls.get_name(name)
        choices = [
            SessionConfigSelectOption(value=item, name=item)
            for item in values
        ]
        return cls(
            id=name,
            name=name,
            description=description,
            category=category,
            type="select",
            currentValue=value,
            options=choices,
            **fields,
        )


class Policy(Select):
    VALUES: ClassVar[list[str]] = [DISABLED, APPROVAL, FULL]

    @classmethod
    def from_value(
        cls,
        name: str,
        value: str = APPROVAL,
        description: str | None = "Tool access policy.",
    ):
        return cls.from_values(
            name=name,
            values=cls.VALUES,
            value=value,
            description=description,
            category="tools",
        )
