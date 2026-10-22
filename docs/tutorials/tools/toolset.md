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
# (1)! Setup shows the tool that the harness made available.
# (2)! This instruction tells the model when to use the tool.
instructions: Use the tools to tell the user facts about themself.
tools:
# (3)! The toolset contributes this tool to the model's available tools.
- UserFactsToolset-AgeTool
agent: DemoHarness
event: model-request
messages:
# (4)! The model receives the user's question.
- kind: user-prompt
  content: How old am I? My name is Maya.
agent: DemoHarness
event: model-response
messages:
# (5)! The model chooses the age tool and supplies its argument.
- kind: tool-call
  tool_name: UserFactsToolset-AgeTool
  args:
    user: Maya
agent: DemoHarness
event: tool-result
# (6)! The tool returns a value for the model to use.
kind: tool-return
tool_name: UserFactsToolset-AgeTool
outcome: success
content: Maya is 34 years old.
agent: DemoHarness
event: model-response
messages:
# (7)! The model turns the tool result into a user-facing answer.
- kind: text
  content: Maya, you're 34 years old.
```

1. Setup records the instruction and the tool made available by the toolset.
2. The instruction gives the model the tool's purpose.
3. The toolset exposes `AgeTool` under its harness-facing name.
4. The request contains the user's question.
5. The model calls the tool with Maya's name.
6. The tool returns the generated age.
7. The model uses that result in its answer.
