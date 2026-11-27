from types import SimpleNamespace

import pytest
from fastmcp import FastMCP
from corio.iterator import ilist
from pydantic_acp import SlashCommandRequest

from xah.commands.policy import Policy
from xah.harness.manager import ToolsetsManager
from xah.options import base as options
from xah.toolsets.base.mcp import ToolsetMCP


def make_deps(*names):
    toolsets = ilist(
        SimpleNamespace(
            name=name,
            POLICY=options.Policies.APPROVAL,
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
    command = Policy(deps=make_deps("Files", "Python"), reset=None)

    result = await command.run()

    policies = dict(line.split(": ", maxsplit=1) for line in result.text.splitlines())

    assert policies == {"Files": "approval", "Python": "approval"}


@pytest.mark.asyncio
async def test_policy_lists_and_sets_mcp_policy():
    server = FastMCP("synthetic-policy-service")

    class SampleMCP(ToolsetMCP):
        URL = server

    manager = ToolsetsManager(
        SimpleNamespace(
            settings=SimpleNamespace(),
            cwd_default=None,
            toolsets_classes=[SampleMCP],
        )
    )
    deps = SimpleNamespace(toolsets=manager)
    mcp = manager.all.name[SampleMCP.name]

    listed = await Policy(deps=deps, reset=None).run()
    policies = dict(line.split(": ", maxsplit=1) for line in listed.text.splitlines())

    assert policies == {mcp.name: options.Policies.FULL}

    await Policy(
        deps=deps,
        name=mcp.name,
        value=options.Policies.DISABLED,
        reset=None,
    ).run()

    assert mcp.options.cls[options.Policy].value == options.Policies.DISABLED
    assert mcp not in manager.permitted


@pytest.mark.asyncio
async def test_policy_gets_toolset_policy():
    deps = make_deps("Files")
    deps.toolsets.all.name["Files"].options.cls[options.Policy].current_value = options.Policies.AUTO
    command = Policy(deps=deps, name="Files", reset=None)

    result = await command.run()

    name, value = result.text.split(": ", maxsplit=1)

    assert name == "Files"
    assert value == options.Policies.AUTO


@pytest.mark.asyncio
async def test_policy_sets_toolset_policy():
    deps = make_deps("Files")
    command = Policy(deps=deps, name="Files", value=options.Policies.FULL, reset=None)

    await command.run()

    assert deps.toolsets.all.name["Files"].options.cls[options.Policy].value == options.Policies.FULL


@pytest.mark.asyncio
async def test_policy_returns_a_helpful_error_for_unknown_toolsets():
    command = Policy(deps=make_deps("Cabinet", "Ledger"), name="PhantomPanel", reset=None)

    result = await command.run()

    assert result.text.startswith("```text")
    assert result.text.endswith("```")
    assert "PhantomPanel" in result.text
    assert "Cabinet" in result.text
    assert "Ledger" in result.text


@pytest.mark.asyncio
async def test_policy_reset_restores_toolset_defaults():
    deps = make_deps("Files", "Python")
    deps.toolsets.all.name["Files"].POLICY = options.Policies.FULL
    deps.toolsets.all.name["Python"].POLICY = options.Policies.AUTO
    for toolset in deps.toolsets.all:
        toolset.options.cls[options.Policy].current_value = options.Policies.DISABLED

    request = SlashCommandRequest(
        name="policy",
        argument="reset",
        raw_prompt="/policy reset",
        session=object(),
        agent=object(),
    )
    await Policy(request=request, deps=deps).run()

    assert deps.toolsets.all.name["Files"].options.cls[options.Policy].value == options.Policies.FULL
    assert deps.toolsets.all.name["Python"].options.cls[options.Policy].value == options.Policies.AUTO
