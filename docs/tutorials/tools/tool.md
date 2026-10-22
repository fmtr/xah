# Define a tool

This exercise introduces the basic shape of a custom tool through a small example that answers a question about a user. It demonstrates how to connect an agent-facing purpose to behavior that returns a result for the agent to use.

```python
--8<-- "xah/examples/m02/e01_tool.py"
```

1. The tool docstring is exposed to the agent, so use it to explain when and why it should call the tool.
2. Tools are Pydantic AI models and support Python type annotations and Pydantic `Field`s.
3. Field descriptions are also exposed to the agent and provide guidance for each argument.
4. The harness calls `run()` when the model selects the tool; its return value is provided back to the model.

This file defines the tool used by the following toolset and harness exercises; it is not a standalone agent to launch.