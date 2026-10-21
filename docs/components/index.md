# Components

Build a custom agent by subclassing `Harness`, setting its instructions, and launching it. This example gives the agent one instruction: answer only with “Hello World.”

```python
--8<-- "examples/e01_hello_world.py"
```

1. The instruction guides the model's replies; the harness otherwise keeps `xah`'s default settings.

Run the file to start the agent server. To chat with it, connect an [ACP client](../acp.md). See [tools](../tools/) to give an agent additional capabilities.

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

1. The setup event shows the instruction and the two management tools available at startup; the agent can enable other toolsets when needed.
2. The user prompt goes to the model, which responds with the requested greeting.
