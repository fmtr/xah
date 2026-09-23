import sys
from pathlib import Path


if __package__ in (None, ""):
    # When an IDE runs this file directly, Python puts the package directory
    # first on sys.path. That makes xah/acp look like top-level acp.
    package_dir = str(Path(__file__).resolve().parent)
    sys.path.remove(package_dir)
    sys.path.insert(0, str(Path(package_dir).parent))

from xah.settings import Settings


def main():
    config = Settings()
    config.run()


if __name__ == "__main__":
    main()
