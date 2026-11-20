import inspect
import pydoc
import sys
from enum import StrEnum, auto
from pathlib import Path


HEADER_MASK = """\
# `{import_path}`

- Type: `{object_type}`
- Module: `{module}`
- Path: `{path}`
"""
SIGNATURE_MASK = """\
## Signature

`{signature}`
"""
DOCUMENTATION_MASK = """\
## Documentation

{docstring}
"""
PUBLIC_MEMBERS_MASK = """\
## Public members

{members}
"""
SOURCE_MASK = """\
## Source

```python
{source}
```
"""
MASK = """\
{header}

{sections}
"""


class PythonObjectType(StrEnum):
    MODULE = auto()
    CLASS = auto()
    FUNCTION = auto()
    METHOD = auto()
    OTHER = auto()


def render(import_path: str) -> str:
    target = pydoc.locate(import_path)
    if target is None:
        raise SystemExit(f"Could not resolve Python import path: {import_path}")

    is_module = inspect.ismodule(target)
    module = target if is_module else inspect.getmodule(target)
    module_file = module.__dict__.get("__file__") if module else None
    module_path = Path(module_file).resolve() if module_file else None
    has_python_source = bool(module_path and module_path.suffix == ".py")

    if is_module:
        object_type = PythonObjectType.MODULE
    elif inspect.isclass(target):
        object_type = PythonObjectType.CLASS
    elif inspect.isfunction(target):
        object_type = PythonObjectType.FUNCTION
    elif inspect.ismethod(target):
        object_type = PythonObjectType.METHOD
    else:
        object_type = PythonObjectType.OTHER

    signature = str(inspect.signature(target)) if callable(target) and has_python_source else None
    source = inspect.getsource(target) if has_python_source else None
    docstring = inspect.getdoc(target)
    public_members = sorted(name for name in dir(target) if not name.startswith("_")) if is_module else []
    path = module_path.relative_to(Path.cwd(), walk_up=True) if module_path else None

    sections = [
        SIGNATURE_MASK.format(signature=signature) if signature else "",
        DOCUMENTATION_MASK.format(docstring=docstring) if docstring else "",
        PUBLIC_MEMBERS_MASK.format(
            members="\n".join(f"- `{name}`" for name in public_members)
        ) if public_members else "",
        SOURCE_MASK.format(source=source.rstrip()) if source else "",
    ]
    header = HEADER_MASK.format(
        import_path=import_path,
        object_type=object_type,
        module=module.__name__ if module else "unavailable",
        path=path if path else "unavailable",
    )
    section_text = "\n".join(section for section in sections if section)

    return MASK.format(header=header.rstrip(), sections=section_text).rstrip()


if __name__ == "__main__":
    print(render(sys.argv[1]))
