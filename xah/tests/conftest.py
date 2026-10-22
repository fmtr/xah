import sys

import pytest


@pytest.fixture(autouse=True)
def isolate_application_cli(monkeypatch):
    """Keep pytest's arguments away from application settings parsers."""
    monkeypatch.setattr(sys, "argv", [sys.argv[0]])
