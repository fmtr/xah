import pytest

from xah.options import base as options


def test_policy_select_exposes_all_values_and_defaults_to_approval():
    policy = options.Policy.from_value("Files")

    assert policy.id == "Files/Policy"
    assert [choice.value for choice in policy.options] == options.Policy.VALUES
    assert policy.current_value == options.Policy.Policies.APPROVAL


@pytest.mark.parametrize(
    ("value", "enabled", "approval"),
    [
        (options.Policy.Policies.DISABLED, False, False),
        (options.Policy.Policies.REQUESTABLE, True, False),
        (options.Policy.Policies.APPROVAL, True, True),
        (options.Policy.Policies.AUTO, True, False),
        (options.Policy.Policies.FULL, True, False),
    ],
)
def test_policy_flags_follow_the_selected_access_mode(value, enabled, approval):
    policy = options.Policy.from_value("Files", value)

    assert policy.enabled is enabled
    assert policy.approval is approval
