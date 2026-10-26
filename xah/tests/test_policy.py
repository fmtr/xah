from types import SimpleNamespace

import pytest
from corio.iterator import ilist
from xah.options import base as options

from xah.commands.policy import Policy


def make_deps(*names):
    toolsets = ilist(
        SimpleNamespace(
            name=name,
            options=SimpleNamespace(
                cls={
                    options.Policy: options.Policy.from_value(name),
                }
            ),
        )
        for name in names
    )
    return SimpleNamespace(toolsets=SimpleNamespace(all=toolsets))


@pytest.mark.asyncio
async def test_policy_lists_toolset_policies():
    command = Policy(deps=make_deps("Files", "Python"))

    result = await command.run()

    assert result.text == "Files: approval\nPython: approval"


@pytest.mark.asyncio
async def test_policy_gets_toolset_policy():
    deps = make_deps("Files")
    deps.toolsets.all.name["Files"].options.cls[options.Policy].current_value = options.Policies.AUTO
    command = Policy(deps=deps, name="Files")

    result = await command.run()

    assert result.text == "Files: auto"


@pytest.mark.asyncio
async def test_policy_sets_toolset_policy():
    deps = make_deps("Files")
    command = Policy(deps=deps, name="Files", value=options.Policies.FULL)

    result = await command.run()

    assert result.text == "Set Files policy to full."
    assert deps.toolsets.all.name["Files"].options.cls[options.Policy].value == options.Policies.FULL
