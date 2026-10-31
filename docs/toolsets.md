# Built-in toolsets

`xah` ships with a collection of toolsets that cover common agent capabilities. A
custom harness can enable the toolsets it needs through its `Toolsets` definition.

## Toolsets

- **Context** — Manage the conversation context, including compacting it when
  needed.
- **Files** — Read, write, edit, move, search, create, and remove files and
  directories.
- **Knowledgebase** — Search and retrieve web pages and fixed collections.
- **Management** — List available toolsets and activate them at runtime.
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
they are needed. The available toolset catalogue does not change during a
session. Activation is one-way for the session; activated toolsets stay active, so
they do not need to be activated again on every turn.

## Shell and background terminals

The Shell tool accepts a `script` argument and runs it in the working directory.
If a command needs adversarial review, the review includes the command as well as
the reasons for the decision. Shell commands have no execution timeout by
default; set `timeout` when a limit is needed.

Long-running commands continue in the background as managed terminals. Their
status messages include a short output tail and how recently output was
produced. The terminal status tool can return summaries for all managed
terminals when called without a terminal ID; use the Files tools to inspect or
search the complete output log.
