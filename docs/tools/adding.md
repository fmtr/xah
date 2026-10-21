# Add and remove tools

You can change a toolset's `Tools` list to add or remove tools. This example starts with the toolset from [Toolsets and tools](toolsets.md), adds `PetTool`, and removes `AgeTool`. The imported `DemoHarness` then offers `PetTool` instead of `AgeTool`.

```python
--8<-- "examples/e03_adding_and_removing_tools.py"
```

1. Add the new tool class to the toolset, then remove the tool you no longer want. `DemoHarness` uses the updated tool list when it starts.
2. `PetTool` returns one of the listed pets for the model to use in its reply.

## Example output

The agent can now call `UserFactsToolset-PetTool`. This sample is illustrative; a real run may choose a different pet.

```yaml
agent: DemoHarness
event: setup
instructions: Use the tools to tell the user facts about themself.
tools:
- UserFactsToolset-PetTool
agent: DemoHarness
event: model-request
messages:
# (1)! The user's question is sent to the model.
- kind: user-prompt
  content: What pet does Maya have?
agent: DemoHarness
event: model-response
messages:
- kind: tool-call
  tool_name: UserFactsToolset-PetTool
  args:
    user_name: Maya
agent: DemoHarness
event: tool-result
# (2)! The return value shows the result from the newly added tool.
kind: tool-return
tool_name: UserFactsToolset-PetTool
outcome: success
content: Maya has an otter as a pet.
agent: DemoHarness
event: model-response
messages:
- kind: text
  content: Maya has an otter as a pet.
```

1. The request shows what the user asked the agent.
2. The tool result is the pet returned to the model.
