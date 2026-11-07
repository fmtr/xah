# Customize a tool by subclassing

This exercise builds on the age lookup by introducing a second kind of response while reusing the existing tool's foundation. It shows how to adapt an example for a new purpose without repeating its setup.

```python
--8<-- "xah/examples/m02/e04_subclassing.py"
```

1. Because `PetTool` uses the same user argument as `AgeTool`, subclassing reuses its definition instead of duplicating it.
2. Override `run()` to change the behavior while retaining the inherited argument.

The next exercise launches a harness that uses this subclass.

## Customize tool-call presentation

Define a tool's input by subclassing `Input` and its structured result by
subclassing `Output`. Their `projection` properties control the ACP
presentation. Xah attaches runtime projection context to `self.request` before
reading either property.

```python
from pydantic import Field
from pydantic_acp.projection import ToolProjection as AcpToolProjection

from xah.toolsets.base.input import Input
from xah.toolsets.base.output import Output
from xah.toolsets.base.tool import Tool


class SearchInput(Input):
    query: str = Field(description="Text to search for.")

    @property
    def projection(self):
        return AcpToolProjection(title=f"Search for {self.query}")


class SearchOutput(Output):
    matches: list[str]

    @property
    def agent(self):
        return self.matches

    @property
    def projection(self):
        return AcpToolProjection(
            title=self.request.tool_name,
            status=self.request.status,
        )


class SearchTool(Tool, SearchInput):
    async def run(self) -> SearchOutput:
        return SearchOutput(matches=[])
```

An input request provides the tool and toolset classes, raw input, working
directory, and computed tool name. An output request also provides the
validated `Input`, serialized output, and call status. This lets output
projections use the original structured result even when `agent` returns a
flattened value or Xah externalizes a large result for the model.

`Output.agent` returns the structured output object by default. Override it
only when the model should receive another representation, such as a list or
string. Override `Input.projection` or `Output.projection` to customize ACP;
there are no `get_agent()` or `get_projection()` compatibility methods.

`Tool.KIND` uses Xah's `Kinds` enum and defaults to `Kinds.OTHER`. Set it to the
kind that best matches the tool's semantics. Clients such as Zed use this kind
to choose how to present a tool call.
