from dataclasses import dataclass, field
from typing import TypeVar

from corio.iterator import enlist, ilist


T = TypeVar("T")


class all:
    pass


@dataclass
class ClassDeclaration[T]:
    all = all

    remove: list[type[T]] | type[all] = field(default_factory=list)
    add: list[type[T]] = field(default_factory=list)

    @classmethod
    def classes(
        cls,
        owner: type,
        declaration_name: str,
        item_name: str,
    ) -> ilist[type[T]]:
        items: dict[str, type[T]] = {}
        for base in reversed(owner.__mro__):
            if declaration_name not in base.__dict__:
                continue

            descriptor = base.__dict__[declaration_name]
            declaration: ClassDeclaration[T] = descriptor.__get__(None, owner)
            if isinstance(declaration, list):
                declaration = cls(add=declaration)

            if declaration.remove is all:
                items.clear()
            else:
                for item in enlist(declaration.remove):
                    items.pop(getattr(item, item_name), None)

            for item in enlist(declaration.add):
                items[getattr(item, item_name)] = item

        return ilist(items.values())
