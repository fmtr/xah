import asyncio
from types import SimpleNamespace

from pydantic_ai import RunContext
from pydantic_ai.usage import RunUsage

from corio import Path
from corio.iterator import ilist
from xah.toolsets.skills.list import List
from xah.toolsets.skills.load import Load
from xah.toolsets.skills.toolset import Skills


def test_list_and_load_construct_per_call_models(tmp_path):
    skill_path = Path(tmp_path / "skills" / "python" / "style")
    skill_path.mkdir(parents=True)
    (skill_path / "SKILL.md").write_text("---\nname: style\ndescription: Python style.\n---\nUse Python style.\n")
    settings = SimpleNamespace(path=SimpleNamespace(skills=Path(tmp_path / "skills"), agents_dir=".agents", skills_dir="skills"))
    toolset = Skills(settings, Path(tmp_path))
    ctx = RunContext(deps=SimpleNamespace(toolsets=ilist([toolset])), model=None, usage=RunUsage())

    assert "python/style" in asyncio.run(List(ctx=ctx).run())
    assert "Use Python style." in asyncio.run(Load(ctx=ctx, skill_ids=["python/style"]).run())
