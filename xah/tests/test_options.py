from xah.options import base as options


def test_policy_values_and_state():
    policy = options.Policy.from_value("Files")

    assert policy.id == "Files/Policy"
    assert policy.value == options.APPROVAL
    assert policy.enabled
    assert policy.approval
    assert [choice.value for choice in policy.options] == options.Policy.VALUES

    policy.current_value = options.FULL

    assert not policy.approval


def test_disabled_policy_is_not_enabled():
    policy = options.Policy.from_value("Files", options.DISABLED)

    assert not policy.enabled
