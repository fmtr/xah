from xah.harness.base import HarnessAcp


class ParentHarness(HarnessAcp):
    pass


class ChildHarness(ParentHarness):
    pass


def test_settings_are_inherited_when_paths_are_unchanged(monkeypatch):
    monkeypatch.setattr("sys.argv", ["pytest"])

    assert ChildHarness.paths is ParentHarness.paths
    assert ChildHarness.Settings is ParentHarness.Settings
