from typing import TypeVar

from corio.iterator import ilist


T = TypeVar("T")


type ClassDeclaration[T] = list[type[T]] | dict[type[T], bool]


def resolve_class_collection(
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
            declaration = dict.fromkeys(declaration, True)

        for item, enabled in declaration.items():
            name = getattr(item, item_name)
            if enabled:
                items[name] = item
            else:
                items.pop(name, None)

    return ilist(items.values())
