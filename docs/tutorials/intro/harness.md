# Build a minimal harness

Start with a minimal agent and give it a simple purpose. This exercise creates an agent that responds only with “Hello World.”

```python
--8<-- "xah/examples/m01/e01_hello.py"
```

1. This instruction is what makes the harness a Hello World agent; the harness otherwise keeps `xah`'s default settings.

Install `xah` with `pip install xah` in the Python environment you will use, then run `python -m xah.examples.m01.e01_hello` to start the agent server. To chat with it, connect an [ACP client](../../acp.md). Continue with the [tool tutorials](../tools/) to give an agent additional capabilities.

## Example output

This shortened sample shows `xah`'s traffic log. The default harness starts with the `Management-Activate` and `Management-List` tools, which it can use to enable other toolsets.

```yaml
agent: HelloWorld
event: setup
# (1)! Setup shows the instructions and tools available to the harness.
# (2)! The instruction controls how the model should respond.
instructions: |-
  You are an agent who only says "Hello World"!
tools:
# (3)! These management tools can enable other toolsets.
- Management-Activate
- Management-List
agent: HelloWorld
event: model-request
messages:
# (4)! The client sends the user's message to the model.
- kind: user-prompt
  content: hi!
agent: HelloWorld
event: model-response
messages:
# (5)! The model returns the agent's answer.
- kind: text
  content: Hello World
```

1. Setup shows the instructions and tools available to the harness.
2. The instruction tells the model to answer only with “Hello World.”
3. The default harness starts with management tools, which can activate other toolsets.
4. The request contains the user's prompt.
5. The response contains the model's final text.
