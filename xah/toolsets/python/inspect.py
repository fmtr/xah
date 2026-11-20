from typing import Annotated, ClassVar

from pydantic import Field

from corio import Path
from xah.toolsets.python.code import PythonCode
from xah.toolsets.base.input import Input as InputBase


class Input(InputBase):
    import_path: Annotated[
        str,
        Field(description="Fully qualified Python import path to a module, class, or function."),
    ]

    @property
    def title(self):
        return f"Inspecting Python import `{self.import_path}`"


class Inspect(PythonCode, Input):
    """Inspect an importable Python module or object in the current environment."""

    SCRIPT: ClassVar[str] = Path.module().with_name("inspect_script.py").read_text()

    @property
    def code(self) -> str:
        return self.SCRIPT

    @property
    def code_args(self) -> tuple[str, ...]:
        return (self.import_path,)
