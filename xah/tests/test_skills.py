import asyncio
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
            description: Python style.
            ---
            Use Python style.
        """)
    )

    tests_path = skills_path / "python" / "tests"
    tests_path.mkdir(parents=True)
    (tests_path / "SKILL.md").write_text(
        strings.trim("""
            ---
            name: tests
            description: Python tests.
            ---
            Use Python tests.
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


def test_skills_instructions_and_load_output(skills_environment):
    toolset = skills_environment.toolset
    ctx = skills_environment.ctx

    assert Skills.get_tool("List", None) is None
    assert Skills.get_tool("Load") is Load

    instructions = asyncio.run(toolset.get_instructions(ctx))
    assert len(instructions) == 1
    available = instructions[0]
    assert available.dynamic
    assert "## Available Skills" in available.content
    assert "Summaries only" in available.content
    assert "Use `Skills-Load`" in available.content
    assert "Python style." in available.content
    assert "Use Python style." not in available.content

    output = asyncio.run(
        Load(ctx=ctx, toolset=toolset, skill_ids=["python/style"]).run()
    )
    assert output.agent == 'Loaded 1 skill into context: "python/style".'
    assert "differ" not in output.model_dump(mode="json")
    assert output.content[0].content.text == output.agent
    assert toolset.skills.id["python/style"].is_loaded

    instructions = asyncio.run(toolset.get_instructions(ctx))
    assert len(instructions) == 2
    loaded, available = instructions
    assert "## Loaded Skills" in loaded.content
    assert "Below are the texts of the skills you have requested." in loaded.content
    assert "Use Python style." in loaded.content
    assert "\n\nPython style." not in loaded.content
    assert "Python tests." in available.content
    assert "Use Python tests." not in available.content

    tool_def = next(iter(toolset.tools.values())).tool_def
    with pytest.raises(ModelRetry, match="Already-loaded skill") as error:
        asyncio.run(
            toolset.validate(ctx, tool_def, {"skill_ids": ["python/style"]})
        )
    assert "already in context" in str(error.value)
    assert "Do not request them again" in str(error.value)
    assert "do not need to be loaded or read on each turn" in str(error.value)


def test_loaded_skill_duplicates_are_validation_errors(skills_environment):
    toolset = skills_environment.toolset
    ctx = skills_environment.ctx

    asyncio.run(Load(ctx=ctx, toolset=toolset, skill_ids=["python/style"]).run())
    tool_def = next(iter(toolset.tools.values())).tool_def
    with pytest.raises(ModelRetry, match="Already-loaded skill"):
        asyncio.run(
            toolset.validate(
                ctx,
                tool_def,
                {"skill_ids": ["python/style", "python/tests"]},
            )
        )

    assert toolset.skills.id["python/style"].is_loaded
    assert not toolset.skills.id["python/tests"].is_loaded

    output = asyncio.run(
        Load(ctx=ctx, toolset=toolset, skill_ids=["python/tests"]).run()
    )
    assert output.agent == 'Loaded 1 skill into context: "python/tests".'
    assert toolset.skills.id["python/tests"].is_loaded


def test_invalid_skill_ids_are_validation_errors(skills_environment):
    toolset = skills_environment.toolset
    ctx = skills_environment.ctx
    tool_def = next(iter(toolset.tools.values())).tool_def

    with pytest.raises(ModelRetry, match="Invalid skill IDs"):
        asyncio.run(
            toolset.validate(ctx, tool_def, {"skill_ids": ["missing/skill"]})
        )


def test_loaded_skills_remain_loaded_after_compaction(skills_environment):
    toolset = skills_environment.toolset
    ctx = skills_environment.ctx
    asyncio.run(
        Load(ctx=ctx, toolset=toolset, skill_ids=["python/style"]).run()
    )

    toolset.after_compress()

    instructions = asyncio.run(toolset.get_instructions(ctx))
    assert len(instructions) == 2
    assert "Use Python style." in instructions[0].content
    assert "\n\nPython style." not in instructions[0].content


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
