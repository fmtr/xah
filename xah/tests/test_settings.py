from corio import Path

from xah.paths import paths
from xah.settings import PathAgent, Settings


def test_path_defaults_and_directories(tmp_path):
    home = Path(tmp_path) / ".workspace"
    path = PathAgent(home=home)

    assert path.home == home
    assert path.agents_dir == ".agents"
    assert path.agents_name == "AGENTS.md"
    assert path.skills_dir == "skills"
    assert path.agents == home / ".agents"
    assert path.skills == home / ".agents" / "skills"
    assert path.sessions == home / "sessions"
    assert home.exists()


def test_path_home_expands_user(tmp_path):
    path = PathAgent(home=Path("~/.workspace"))

    assert path.home == Path.home() / ".workspace"


def test_settings_uses_xah_paths_and_environment_prefix():
    assert Settings.paths is paths
    assert Settings.get_env_prefix() == "XAH__"


def test_path_directories_are_settable(tmp_path):
    path = PathAgent(
        home=Path(tmp_path),
        agents_dir=".project",
        agents_name="ROOT.md",
        skills_dir="skills-dir",
        agents=Path(tmp_path) / "custom-agents",
    )

    assert path.agents_dir == ".project"
    assert path.agents_name == "ROOT.md"
    assert path.skills_dir == "skills-dir"
    assert path.agents == Path(tmp_path) / "custom-agents"
    assert path.skills == Path(tmp_path) / "custom-agents" / "skills-dir"
