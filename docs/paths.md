# Paths, instructions, and skills

`xah` keeps user data separate from project instructions and skills. Its defaults are:

| Purpose | Default path |
| --- | --- |
| User data home | `~/.xah/` |
| ACP session store | `~/.xah/sessions/` |
| User-level agent instructions | `~/.xah/.agents/AGENTS.md` |
| User-level skills | `~/.xah/.agents/skills/` |
| Project-level instructions | `<working directory>/.agents/AGENTS.md` |
| Project-level skills | `<working directory>/.agents/skills/` |

Project paths are based on the working directory supplied by the ACP client when it creates a session. `xah` reads user and project `AGENTS.md` files when present. It discovers skills in both skills folders; a project skill takes precedence when an ID appears in both. Session data is stored under the user data home.

You can customize these locations through the `path` settings. `home` changes where sessions and user-level files are stored; `agents_dir` and `skills_dir` choose the instruction and skills folders; `agents_name` changes the instruction filename. These settings are defined by `PathAgent` in [`xah/settings.py`](https://github.com/fmtr/xah/blob/main/xah/settings.py).

## Skills

Skills use the [Agent Skills format](https://agentskills.io/specification): a folder containing `SKILL.md`, with YAML frontmatter for `name` and `description`, followed by Markdown instructions. For example, save this file as `.agents/skills/python/style/SKILL.md`:

```markdown
---
name: style
description: Conventions for Python code in this project.
---

# Python style

Prefer clear names and small, direct changes.
```

The `name` is required metadata and, under the Agent Skills specification, should match the skill folder's name (`style` in this example). When skills are nested, `xah` identifies them by their path relative to the skills folder, such as `python/style`; use that ID when listing or loading a skill. User-level skills go under `~/.xah/.agents/skills/` instead.

`AGENTS.md` is separate from a skill: use it for instructions that should apply to every relevant session, and use skills for detailed guidance that can be discovered and loaded when needed.
