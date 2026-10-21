# Toolsets and tools

A toolset groups related tools. Each tool is a Python class: its fields describe the arguments the model can provide, and its `run()` method performs the action.

This example creates a `DemoHarness` with a `UserFactsToolset`. Its `Toolsets` declaration replaces the default toolsets, so only the custom toolset is available. The toolset's `Tools` declaration makes `AgeTool` available to the agent.

```python
--8<-- "examples/e02_toolset_and_tool.py"
```

1. This harness uses only the toolsets returned here; add any built-in or custom toolsets you want alongside the custom one.
2. Put each tool class in its toolset's `Tools` list to make it available to the agent.
3. The harness calls `run()` when the model chooses this tool. This example returns a random age for demonstration.

## Example output

The model selects `UserFactsToolset-AgeTool`, the tool returns a result, and the model uses it in its reply. The log below is illustrative; actual values and wording vary.

```yaml
agent: DemoHarness
event: setup
instructions: Use the tools to tell the user facts about themself.
tools:
- UserFactsToolset-AgeTool
agent: DemoHarness
event: model-request
messages:
# (1)! The prompt is logged as a user-prompt.
- kind: user-prompt
  content: How old am I? My name is Maya.
agent: DemoHarness
event: model-response
messages:
- kind: tool-call
  tool_name: UserFactsToolset-AgeTool
  args:
    user_name: Maya
agent: DemoHarness
event: tool-result
# (2)! The tool's return value is logged so you can see what the model receives.
kind: tool-return
tool_name: UserFactsToolset-AgeTool
outcome: success
content: Maya is 34 years old.
agent: DemoHarness
event: model-response
messages:
- kind: text
  content: Maya, you're 34 years old.
```

1. The model request includes the user's question and name.
2. The `tool-result` event records the value returned by `AgeTool`; this sample age is made up.
