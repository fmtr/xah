# Group tools in a toolset

This exercise groups the tool from [Define a tool](tool.md) into a toolset, creating a reusable collection of related capabilities for an agent.

```python
--8<-- "xah/examples/m02/e02_toolset.py"
```

1. The toolset exposes each tool class listed here to the agent.

This toolset is connected to an agent in [Make a toolset available to a harness](harness.md). The sample output below shows what a run of that harness looks like when it uses the grouped tool.

## Example output

```yaml
agent: DemoHarness
event: setup
instructions: Use the tools to tell the user facts about themself.
tools:
- UserFactsToolset-AgeTool
agent: DemoHarness
event: model-request
messages:
- kind: user-prompt
  content: How old am I? My name is Maya.
agent: DemoHarness
event: model-response
messages:
- kind: tool-call
  tool_name: UserFactsToolset-AgeTool
  args:
    user: Maya
agent: DemoHarness
event: tool-result
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