import asyncio
from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.usage import RunUsage

from corio import Path
from corio.iterator import ilist
from xah.constants import HARNESS_FEEDBACK
from xah.toolsets.skills.list import List
from xah.toolsets.base.tool import Validation
from xah.toolsets.skills.list import List
from xah.toolsets.skills.load import CheckDupes, Load
from xah.toolsets.skills.toolset import Skills


def test_list_and_load_construct_per_call_models(tmp_path):
    skill_path = Path(tmp_path / "skills" / "python" / "style")
    skill_path.mkdir(parents=True)
    (skill_path / "SKILL.md").write_text("---\nname: style\ndescription: Python style.\n---\nUse Python style.\n")
    other_skill_path = Path(tmp_path / "skills" / "python" / "tests")
    other_skill_path.mkdir(parents=True)
    (other_skill_path / "SKILL.md").write_text("---\nname: tests\ndescription: Python tests.\n---\nUse Python tests.\n")
    settings = SimpleNamespace(path=SimpleNamespace(skills=Path(tmp_path / "skills"), agents_dir=".agents", skills_dir="skills"))
    toolset = Skills(settings, Path(tmp_path))
    ctx = RunContext(
        deps=SimpleNamespace(toolsets=ilist([toolset]), approval_bridge=None),
        model=None,
        usage=RunUsage(),
        pending_messages=[],
    )

    listed = asyncio.run(List(ctx=ctx, toolset=toolset).run())
    assert "python/style" in listed
    assert "Summaries only" not in listed
    content = ctx.pending_messages[0].messages[0].parts[0].content
    assert content.startswith(HARNESS_FEEDBACK)
    assert "Summaries only" in content
    assert "Use Python style." in asyncio.run(Load(ctx=ctx, toolset=toolset, skill_ids=["python/style"]).run())
    assert toolset.history == {"python/style"}
    remaining = asyncio.run(List(ctx=ctx, toolset=toolset).run())
    assert "Python tests." in remaining
    assert "Python style." not in remaining

    asyncio.run(Load(ctx=ctx, toolset=toolset, skill_ids=["python/tests"]).run())
    with pytest.raises(ModelRetry, match="already been read"):
        asyncio.run(List(ctx=ctx, toolset=toolset).run())


def test_loading_a_skill_twice_requires_compaction(tmp_path):
    skill_path = Path(tmp_path / "skills" / "python" / "style")
    skill_path.mkdir(parents=True)
    (skill_path / "SKILL.md").write_text("---\nname: style\ndescription: Python style.\n---\nUse Python style.\n")
    settings = SimpleNamespace(path=SimpleNamespace(skills=Path(tmp_path / "skills"), agents_dir=".agents", skills_dir="skills"))
    toolset = Skills(settings, Path(tmp_path))
    ctx = RunContext(
        deps=SimpleNamespace(toolsets=ilist([toolset]), approval_bridge=None),
        model=None,
        usage=RunUsage(),
        pending_messages=[],
    )
    toolset.history.add("python/style")
    validator = CheckDupes(ctx=ctx, toolset=toolset, skill_ids=["python/style"])

    with pytest.raises(ModelRetry, match="python/style"):
        validator.validation = Validation()
        asyncio.run(validator.validate())

    toolset.after_compress()
    assert toolset.history == set()
