import os

from corio import Path
from xah.options import base as options
from corio.paths import PackagePaths


class SelectPath(options.Select):
    cwd: Path

    @classmethod
    def from_cwd(
        cls,
        name: str | None = None,
        *,
        cwd: Path,
        value: str = ".",
        description: str = "Directory available to tools.",
    ):
        directories = []
        for current, child_directories, _files in os.walk(cwd):
            child_directories[:] = [
                child
                for child in child_directories
                if not child.startswith(".")
                and child not in {"__pycache__", "node_modules"}
            ]
            current_path = Path(current)
            directories.extend(
                (current_path / child).relative_to(cwd).as_posix()
                for child in child_directories
            )

        values = [
            "/",
            PackagePaths.dev_repo.as_posix(),
            ".",
            *sorted(directories, key=str.casefold),
        ]
        return cls.from_values(
            name=name,
            values=values,
            value=value,
            description=description,
            cwd=cwd.resolve(),
        )

    @property
    def value(self) -> Path:
        return (self.cwd / self.current_value).resolve()


class PathCwd(SelectPath):
    VISIBLE = False


class PathRead(SelectPath):
    pass


class PathWrite(SelectPath):
    pass
