from typing import Annotated, ClassVar

from pydantic import Field
from acp.schema import FileEditToolCallContent

from corio import Path, function
from xah.toolsets.python.code import PythonCode
from xah.toolsets.base.input import Input as InputBase
from xah.toolsets.base.projection.base import ProjectionContent
from xah.toolsets.terminal.base import TerminalOutput


class Input(InputBase):
    import_path: Annotated[
        str,
        Field(description="Fully qualified Python import path to a module, class, or function."),
    ]

    @property
    def title(self):
        return f"Inspecting Python import `{self.import_path}`"


class InspectOutput(TerminalOutput):
    @property
    def content(self) -> list[ProjectionContent]:
        return [
            self.content_block(self.summary),
            FileEditToolCallContent(
                type="diff",
                path=str(self.terminal.output_path),
                old_text="",
                new_text=self.tail,
            ),
        ]


class Inspect(PythonCode, Input):
    """
    Inspect an importable Python module, class, function, or object by its fully qualified path.

    Returns its type, module and file location, available line range and signature, documentation, and public module members. Source code is not included.
    """

    SCRIPT: ClassVar[str] = Path.module().with_name("inspect_script.py").read_text()

    @function.ccp
    def Output(cls) -> type[InspectOutput]:
        return InspectOutput

    @property
    def code(self) -> str:
        return self.SCRIPT

    @property
    def code_args(self) -> tuple[str, ...]:
        return (self.import_path,)
