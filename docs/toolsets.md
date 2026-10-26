# Built-in toolsets

`xah` ships with a collection of toolsets that cover common agent capabilities. A
custom harness can enable the toolsets it needs through its `Toolsets` definition.

## Toolsets

- **Context** — Manage the conversation context, including compacting it when
  needed.
- **Files** — Read, write, edit, move, search, create, and remove files and
  directories.
- **Knowledgebase** — Search and retrieve web pages and fixed collections.
- **Management** — List and activate toolsets at runtime.
- **Python** — Run Python code, manage packages, and run tests.
- **Shell** — Execute shell commands.
- **Skills** — Discover and load agent skills.
- **Subagent** — Delegate tasks to subagents.
- **Terminals** — Start and manage background shell commands.
- **Todo** — Manage a todo list and its task statuses.
- **Utils** — General-purpose utilities, including pausing execution for a fixed
  duration.
- **Web** — Search and research the web.

The default `xah` harness enables Context, Files, Terminals, Shell, Python,
Skills, Todo, Utils, and Management. Knowledgebase, Subagent, and Web are also
included in the built-in catalogue and can be enabled by a custom harness when
they are needed.
