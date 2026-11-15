from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.usage import RunUsage

from corio import Path, strings
from corio.iterator import ilist
from xah.toolsets.skills.load import Load
from xah.toolsets.skills.toolset import Skills


@pytest.fixture
def skills_environment(tmp_path):
    skills_path = Path(tmp_path / "skills")
    style_path = skills_path / "python" / "style"
    style_path.mkdir(parents=True)
    (style_path / "SKILL.md").write_text(
        strings.trim("""
            ---
            name: style
            description: Style summary.
            ---
            STYLE-BODY-MARKER-61A4
        """)
    )

    tests_path = skills_path / "python" / "tests"
    tests_path.mkdir(parents=True)
    (tests_path / "SKILL.md").write_text(
        strings.trim("""
            ---
            name: tests
            description: Test summary.
            ---
            TEST-BODY-MARKER-92BC
        """)
    )

    settings = SimpleNamespace(
        path=SimpleNamespace(
            skills=skills_path,
            agents_dir=".agents",
            skills_dir="skills",
        )
    )
    toolset = Skills(settings, Path(tmp_path))
    ctx = RunContext(
        deps=SimpleNamespace(toolsets=ilist([toolset]), approval_bridge=None),
        model=None,
        usage=RunUsage(),
        pending_messages=[],
    )
    return SimpleNamespace(toolset=toolset, ctx=ctx)


@pytest.mark.asyncio
async def test_skills_instructions_and_load_output(skills_environment):
    toolset = skills_environment.toolset
    ctx = skills_environment.ctx

    assert Skills.get_tool("List", None) is None
    assert Skills.get_tool("Load") is Load

    instructions = await toolset.get_instructions(ctx)
    assert len(instructions) == 1
    available = instructions[0]
    assert available.dynamic
    assert "python/style" in available.content
    assert "Style summary." in available.content
    assert "STYLE-BODY-MARKER-61A4" not in available.content

    output = await Load(
        ctx=ctx,
        toolset=toolset,
        skill_ids=["python/style"],
    ).run()
    assert output.skill_ids == ["python/style"]
    assert output.loaded == []
    assert toolset.skills.id["python/style"].is_loaded

    instructions = await toolset.get_instructions(ctx)
    assert len(instructions) == 2
    loaded, available = instructions
    assert "STYLE-BODY-MARKER-61A4" in loaded.content
    assert "TEST-BODY-MARKER-92BC" not in loaded.content
    assert "Test summary." in available.content
    assert "TEST-BODY-MARKER-92BC" not in available.content

    tool_def = next(iter(toolset.tools.values())).tool_def
    with pytest.raises(ModelRetry) as error:
        await toolset.validate(ctx, tool_def, {"skill_ids": ["python/style"]})
    assert "python/style" in str(error.value)


@pytest.mark.asyncio
async def test_loaded_skill_duplicates_are_validation_errors(skills_environment):
    toolset = skills_environment.toolset
    ctx = skills_environment.ctx

    await Load(ctx=ctx, toolset=toolset, skill_ids=["python/style"]).run()
    tool_def = next(iter(toolset.tools.values())).tool_def
    with pytest.raises(ModelRetry) as error:
        await toolset.validate(
            ctx,
            tool_def,
            {"skill_ids": ["python/style", "python/tests"]},
        )

    assert "python/style" in str(error.value)

    assert toolset.skills.id["python/style"].is_loaded
    assert not toolset.skills.id["python/tests"].is_loaded

    output = await Load(ctx=ctx, toolset=toolset, skill_ids=["python/tests"]).run()
    assert output.skill_ids == ["python/tests"]
    assert toolset.skills.id["python/tests"].is_loaded


@pytest.mark.asyncio
async def test_invalid_skill_ids_are_validation_errors(skills_environment):
    toolset = skills_environment.toolset
    ctx = skills_environment.ctx
    tool_def = next(iter(toolset.tools.values())).tool_def

    with pytest.raises(ModelRetry) as error:
        await toolset.validate(ctx, tool_def, {"skill_ids": ["missing/skill"]})

    assert "missing/skill" in str(error.value)


@pytest.mark.asyncio
async def test_loaded_skills_remain_loaded_after_compaction(skills_environment):
    toolset = skills_environment.toolset
    ctx = skills_environment.ctx
    await Load(ctx=ctx, toolset=toolset, skill_ids=["python/style"]).run()

    toolset.after_compress()

    instructions = await toolset.get_instructions(ctx)
    assert len(instructions) == 2
    assert "STYLE-BODY-MARKER-61A4" in instructions[0].content
    assert "STYLE-BODY-MARKER-61A4" not in instructions[1].content


def test_skill_discovery_requires_frontmatter(tmp_path):
    skill_path = Path(tmp_path / ".agents" / "skills" / "example")
    skill_path.mkdir(parents=True)
    settings = SimpleNamespace(
        path=SimpleNamespace(
            skills=Path(tmp_path / "global-skills"),
            agents_dir=".agents",
            skills_dir="skills",
        )
    )

    (skill_path / "SKILL.md").write_text(
        strings.trim("""
            # Example
            Use this guidance.
        """)
    )
    without_frontmatter = Skills(settings, Path(tmp_path))
    assert [skill.id for skill in without_frontmatter.skills] == []

    (skill_path / "SKILL.md").write_text(
        strings.trim("""
            ---
            name: example
            description: Example guidance.
            ---
            Use this guidance.
        """)
    )
    with_frontmatter = Skills(settings, Path(tmp_path))
    assert [skill.id for skill in with_frontmatter.skills] == ["example"]
