from enum import auto
from typing import Any, ClassVar

from acp.schema import SessionConfigOptionSelect, SessionConfigSelectOption
from corio.enums import MapEnum


class Policies(MapEnum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name.lower()

    DISABLED = auto(), "The tool is unavailable."
    REQUESTABLE = auto(), "The tool is available after an approval request."
    APPROVAL = auto(), "The tool is available with approval for every call."
    AUTO = auto(), "The tool is available, but warnings require approval."
    FULL = auto(), "The tool is available without approval."


class Select(SessionConfigOptionSelect):
    VISIBLE: ClassVar[bool] = True

    @property
    def value(self) -> str:
        return self.current_value

    @property
    def enabled(self) -> bool:
        return self.value != Policies.DISABLED

    @property
    def approval(self) -> bool:
        return self.current_value == Policies.APPROVAL

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
        **fields: Any,
    ):
        name = cls.get_name(name)
        choices = []
        for item in values:
            option_description = None
            if isinstance(item, MapEnum):
                option_description = item.description
            choices.append(
                SessionConfigSelectOption(
                    value=item,
                    name=item,
                    description=option_description,
                )
            )
        return cls(
            id=name,
            name=name,
            description=description,
            type="select",
            currentValue=value,
            options=choices,
            **fields,
        )


class Policy(Select):
    Policies: ClassVar[type[Policies]] = Policies
    VALUES: ClassVar[list[Policies]] = list(Policies)

    @classmethod
    def from_value(
        cls,
        name: str,
        value: str = Policies.APPROVAL,
        description: str | None = "Tool access policy.",
    ):
        return cls.from_values(
            name=name,
            values=cls.VALUES,
            value=value,
            description=description,
        )
