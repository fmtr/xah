# `xah`

## What does it stand for?

**eXtensible Agent Harness**—or perhaps “Not Another Harness!”

## How is it pronounced?

The *a* is silent.

## Should I use `xah`?

`xah` is for people comfortable with Python development—directly or via agents—who want fine-grained control over how their agents behave.

### Who might find it useful?

`xah` may be useful if you want to:

- Work with locally hosted models, whose tool discipline may not always be reliable.
- Add custom tools—for example, ensure the agent can only run the right version of Python.
- Add validation that blocks misbehavior even when prompts asking the agent not to do something have failed.
- Add tools that aren't typically available in existing harnesses.
- Subclass or extend existing tools, validation workflows, or subagents.
- Extend agents to non-coding workflows.

### Who is `xah` not for?

- If you use frontier models exclusively and they already behave roughly how you want, a mainstream off-the-shelf agent may be a better fit.
- If you do not want to work in Python or maintain code-level customizations, `xah`'s main strength—extending the harness in Python—may not be useful to you.

## Why does `xah` exist?

There are two main motivations for `xah`: extensibility, and adapting ACP for agents beyond coding.

### Extensibility

Existing harnesses can be limiting when a developer—or an agent working with them—needs to develop tools in a fine-grained, debuggable way. Common approaches tend to fall into a few groups:

- **Instructions:** add more context in files such as `AGENTS.md` or skills, then hope the agent follows it.
- **Configuration:** set coarse-grained options for behavior and permissions.
- **Plugin systems:** gain more power, but learn a separate workflow; plugins can also be difficult to debug when they run through the agent.

These approaches have their place, but they aren't a substitute for being able to change the harness directly. `xah` makes it straightforward to develop and debug custom tools and validation as Python code. A prompt can ask an agent not to misbehave; code can block it from doing so.

`xah` is built on [Pydantic AI](https://ai.pydantic.dev/) and [Pydantic Deep Agents](https://vstorm-co.github.io/pydantic-deepagents/).

### Adapting ACP for non-coding agents

The [Agent Client Protocol (ACP)](https://agentclientprotocol.com/) is designed to connect coding agents with clients such as editors and IDEs. It provides a standard communication interface, rather than a bespoke integration for every agent and client. ACP is not an agent-to-agent coordination protocol.

`xah` begins with the familiar coding-agent use case—an IDE, terminal UI, or similar client—and explores using that client experience with agents for other kinds of work, too.

## Get started

Install `xah` from PyPI and start the server:

```bash
pip install xah
xah
```

For an ephemeral run, use `uvx xah`. The server needs an ACP client for the interactive interface. See the [quick start](https://fmtr.github.io/xah/quick/) and [PyCharm](https://fmtr.github.io/xah/acp/#pycharm) or [Zed](https://fmtr.github.io/xah/acp/#zed) setup instructions, then work through the [tutorials](https://fmtr.github.io/xah/tutorials/) to extend `xah`.

## Documentation

Visit the [`xah` documentation](https://fmtr.link/xah/doc) for setup, ACP client configuration, tutorials, and agent data and skills.
