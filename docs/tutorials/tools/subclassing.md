# Customize a tool by subclassing

This exercise builds on the age lookup by introducing a second kind of response while reusing the existing tool's foundation. It shows how to adapt an example for a new purpose without repeating its setup.

```python
--8<-- "xah/examples/m02/e04_subclassing.py"
```

1. Because `PetTool` uses the same user argument as `AgeTool`, subclassing reuses its definition instead of duplicating it.
2. Override `run()` to change the behavior while retaining the inherited argument.

The next exercise launches a harness that uses this subclass.

## Customize tool-call presentation

Each tool selects projection classes through `Tool.projections`. The default is
Xah's base `Projection`, which supplies a concise tool-name title and reports
progress status. ACP passes call data to a short-lived projection instance at
construction; `start()` and `progress()` take no call-specific arguments.

```python
from corio.function import ccp
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.projection import Projection
from xah import Tool


class SearchProjection(Projection):
    def start(self):
        return AcpToolProjection(title=f"Searching for {self.raw_input['query']}")


class SearchTool(Tool):
    @ccp
    def projections(cls) -> list[type[Projection]]:
        return [SearchProjection]
```

The optional `self.sig` value is available when the tool has a dedicated
`Signature` model and the call input validates against it. Otherwise it is
`None`; `self.raw_input` remains available either way. Signatures provide a
separate home for argument fields and metadata, but current production tools do
not yet declare them.

`Tool.KIND` uses Xah's `Kinds` enum and defaults to `Kinds.OTHER`. Set it to the
kind that best matches the tool's semantics. Clients such as Zed use this kind
to choose how to present a tool call.

Xah's first-pass ACP maps intentionally provide only the minimal base
presentation. They no longer register pydantic-acp's filesystem and Bash maps,
so their rich diff, search-tree, read-preview, and command rendering is not
included. Focused Xah projection subclasses for those presentations are a
later phase. Raw input and output are still carried as projection context for
future renderers.
