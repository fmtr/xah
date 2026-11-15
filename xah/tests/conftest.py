import sys

import pytest


@pytest.fixture(autouse=True)
def isolate_application_settings(monkeypatch):
    """Keep test values from leaking into application settings parsing."""
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setattr(sys, "argv", [sys.argv[0]])
