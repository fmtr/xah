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
# (1)! Setup shows the custom instruction and tool exposed by the harness.
# (2)! The harness passes this instruction to the model.
instructions: Use the tools to tell the user facts about themself.
tools:
# (3)! The toolset makes this tool available to the model.
- UserFactsToolset-AgeTool
agent: DemoHarness
event: model-request
messages:
# (4)! The user's prompt is sent to the model.
- kind: user-prompt
  content: How old am I? My name is Maya.
agent: DemoHarness
event: model-response
messages:
# (5)! The model asks the harness to run the age tool.
- kind: tool-call
  tool_name: UserFactsToolset-AgeTool
  args:
    user: Maya
agent: DemoHarness
event: tool-result
# (6)! The tool's return value is logged so the model can use it.
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

1. Setup shows the custom instruction and tool exposed by the harness.
2. The harness passes its instruction to the model.
3. The toolset makes `AgeTool` available.
4. The request contains the user's question.
5. The model calls `AgeTool` with Maya's name.
6. The tool returns the age for the model to use.
