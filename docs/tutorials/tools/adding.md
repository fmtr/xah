# Add and remove tools

This final exercise revisits the harness and toolset from the earlier examples, changing the capability the agent offers. It demonstrates how to evolve the available tools as an agent's purpose changes.

```python
--8<-- "xah/examples/m02/e05_adding.py"
```

1. Add `PetTool` to the toolset so `DemoHarness` can use it.
2. Remove `AgeTool` to leave only the pet lookup tool available.

Install `xah` with `pip install xah` in the Python environment you will use, then run `python -m xah.examples.m02.e05_adding` and ask what pet a user has. The agent can now call `UserFactsToolset-PetTool`; this sample is illustrative, and a real run may choose a different pet.

## Example output

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
    user: Maya
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
