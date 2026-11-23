import inspect
import pydoc
import sys
from contextlib import redirect_stderr, redirect_stdout
from enum import StrEnum, auto
from functools import cached_property
from io import StringIO
from pathlib import Path


UNAVAILABLE = "[unavailable]"
MASK = """\
Import: {import_path}
Type: {object_type}
Module: {module}
Path: {path}
Lines: {line_range}
Signature: {signature}
Members: {members}
Documentation:
{docstring}
"""


class PythonObjectType(StrEnum):
    MODULE = auto()
    CLASS = auto()
    FUNCTION = auto()
    METHOD = auto()
    OTHER = auto()


class Inspection:
    def __init__(self, import_path: str):
        self.import_path = import_path

    @cached_property
    def target(self):
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            target = pydoc.locate(self.import_path)
        if target is None:
            raise SystemExit(f"Could not resolve Python import path: {self.import_path}")
        return target

    @cached_property
    def is_module(self):
        return inspect.ismodule(self.target)

    @cached_property
    def module(self):
        if self.is_module:
            return self.target
        return inspect.getmodule(self.target)

    @cached_property
    def module_path(self):
        if not self.module:
            return None

        module_file = self.module.__dict__.get("__file__")
        if not module_file:
            return None
        return Path(module_file).resolve()

    @cached_property
    def has_python_source(self):
        if not self.module_path:
            return False
        return self.module_path.suffix == ".py"

    @cached_property
    def object_type(self):
        if self.is_module:
            return PythonObjectType.MODULE
        if inspect.isclass(self.target):
            return PythonObjectType.CLASS
        if inspect.isfunction(self.target):
            return PythonObjectType.FUNCTION
        if inspect.ismethod(self.target):
            return PythonObjectType.METHOD
        return PythonObjectType.OTHER

    @cached_property
    def module_name(self):
        if not self.module:
            return UNAVAILABLE
        return self.module.__name__

    @cached_property
    def path(self):
        if not self.module_path:
            return UNAVAILABLE
        return str(self.module_path.relative_to(Path.cwd(), walk_up=True))

    @cached_property
    def line_range(self):
        if not self.has_python_source:
            return UNAVAILABLE

        source_lines, first_line = inspect.getsourcelines(self.target)
        line_start = first_line or 1
        last_line = line_start + len(source_lines) - 1
        return f"{line_start}-{last_line}"

    @cached_property
    def signature(self):
        if not callable(self.target) or not self.has_python_source:
            return UNAVAILABLE
        return str(inspect.signature(self.target))

    @cached_property
    def members(self):
        if not self.is_module:
            return UNAVAILABLE
        public_members = sorted(name for name in dir(self.target) if not name.startswith("_"))
        return ", ".join(public_members) or UNAVAILABLE

    @cached_property
    def docstring(self):
        return inspect.getdoc(self.target) or UNAVAILABLE

    @cached_property
    def text(self):
        return MASK.format(
            import_path=self.import_path,
            object_type=self.object_type,
            module=self.module_name,
            path=self.path,
            line_range=self.line_range,
            signature=self.signature,
            members=self.members,
            docstring=self.docstring,
        ).rstrip()


if __name__ == "__main__":
    print(Inspection(sys.argv[1]).text)
