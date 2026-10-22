# Make a toolset available to a harness

This exercise connects the toolset from [Group tools in a toolset](toolset.md) to a harness, bringing the earlier examples together into an agent that can use the custom capability.

```python
--8<-- "xah/examples/m02/e03_harness.py"
```

1. This declaration replaces the default toolsets. Add any built-in or custom toolsets you also want the harness to have available.

Install `xah` with `pip install xah` in the Python environment you will use, then run `python -m xah.examples.m02.e03_harness` to start the agent server, then connect an [ACP client](../../acp.md). With the tool available, the model can request an age and use its result in a reply. This sample log shows the flow; actual ages and wording vary.

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
# (1)! The user's prompt is sent to the model.
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
