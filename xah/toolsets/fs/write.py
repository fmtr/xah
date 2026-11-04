from typing import Annotated

from xah.class_collections import classes
from pydantic import Field

from corio import Path
from corio.function import ccp, cp
from xah.class_collections import classes
from xah.toolsets.base.projection import FileEditProjection
from xah.toolsets.base.tool import Kinds, Signature as SignatureBase, Tool
from xah.toolsets.fs.permissions import Permissions
from xah.toolsets.fs.similarity import SimilarityValidator


class Projection(FileEditProjection):
    @cp
    def new_text(self) -> str:
        return self.sig.content


class Signature(SignatureBase):
    path: Annotated[Path, Permissions(Permissions.Write)] = Field(
        description="Destination path relative to the working directory.",
    )
    content: str = Field(description="Complete file content to write.")


class Write(Tool, Signature):
    """Write complete content to a file."""

    KIND = Kinds.EDIT

    @ccp
    def Projection(cls):
        return Projection

    @classes
    def Validators(cls):
        return [WriteWarnings]

    async def run(self) -> str:
        self.path.parent.mkdirf()
        self.path.write_text(self.content)
        return f"Wrote {len(self.content.splitlines())} lines to {self.path}"


class WriteWarnings(SimilarityValidator, Write):
    async def validate(self):
        if not self.path.is_file():
            return

        current = self.path.read_text(errors="replace")
        messages = self.similarity_warnings(
            current,
            self.content,
            "You are overwriting a file with {similarity}% similar content. Use partial reads and edits for small changes.",
        )
        self.messages.extend(messages)
