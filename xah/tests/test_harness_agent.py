from types import SimpleNamespace

from corio import Path
from pydantic_ai.models.test import TestModel

from xah.harness.base import Harness, HarnessAcp
from xah.harness.deps import HarnessAgentDeps, HarnessDeps


def test_harness_agent_is_directly_usable():
    agent = Harness(
        model=TestModel(),
        cwd_default=Path.cwd(),
        settings=SimpleNamespace(),
    )

    assert isinstance(agent.deps, HarnessAgentDeps)
    assert agent.deps.toolsets == []
    assert agent.agent_capabilities == [
        agent.stuck_loop_detection,
        agent.model_traffic_logger,
    ]


def test_harness_deps_adds_approval_behavior_to_agent_deps():
    assert issubclass(HarnessDeps, HarnessAgentDeps)
    assert Harness is not HarnessAcp
