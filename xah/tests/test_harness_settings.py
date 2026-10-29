from xah.harness.base import HarnessAcp, select_acp_subprotocol


class ParentHarness(HarnessAcp):
    pass


class ChildHarness(ParentHarness):
    pass


def test_settings_are_inherited_when_paths_are_unchanged(monkeypatch):
    monkeypatch.setattr("sys.argv", ["pytest"])

    assert ChildHarness.paths is ParentHarness.paths
    assert ChildHarness.Settings is ParentHarness.Settings


def test_acp_subprotocol_is_negotiated_when_offered():
    assert select_acp_subprotocol(None, ["acp.v1"]) == "acp.v1"


def test_acp_subprotocol_is_optional_for_clients_that_do_not_offer_it():
    assert select_acp_subprotocol(None, []) is None
