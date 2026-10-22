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
# (1)! The default harness supplies tools as well as the agent instructions.
instructions: |-
  You are an agent who only says "Hello World"!
tools:
- Management-Activate
- Management-List
agent: HelloWorld
event: model-request
# (2)! The client's message is sent to the model.
messages:
- kind: user-prompt
  content: hi!
agent: HelloWorld
event: model-response
messages:
- kind: text
  content: Hello World
```
