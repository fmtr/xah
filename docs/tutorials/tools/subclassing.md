# Customize a tool by subclassing

This exercise builds on the age lookup by introducing a second kind of response while reusing the existing tool's foundation. It shows how to adapt an example for a new purpose without repeating its setup.

```python
--8<-- "xah/examples/m02/e04_subclassing.py"
```

1. Because `PetTool` uses the same user argument as `AgeTool`, subclassing reuses its definition instead of duplicating it.
2. Override `run()` to change the behavior while retaining the inherited argument.

The next exercise launches a harness that uses this subclass.

## Customize tool-call presentation

By default, `xah` formats tool input and output for the ACP client. A tool can
replace that presentation by returning a custom `Projection` class:

```python
from corio.function import ccp
from pydantic_acp.projection import ToolProjection as AcpToolProjection
from xah.toolsets.base.projection import Projection
from xah import Kinds, Tool


class SearchProjection(Projection):
    def start(self, *, raw_input, cwd):
        return AcpToolProjection(title=f"Searching for {raw_input['query']}")


class SearchTool(Tool):
    KIND = Kinds.SEARCH

    @ccp
    def Projection(cls) -> type[Projection]:
        return SearchProjection
```

`Tool.KIND` uses Xah's `Kinds` enum and defaults to `Kinds.OTHER`. Set it to the
kind that best matches the tool's semantics. Current tools that execute actions
use `Kinds.OTHER`; `Kinds.EXECUTE` is available for ACP compatibility. Clients
such as Zed use the kind to choose how to present a tool call. In particular,
Zed shows ordinary tool content for `read` and `search` calls. Xah sends
`rawInput` and `rawOutput` separately and keeps the default title concise.

Override `start()` to customize the initial display and `progress()` to
customize updates as the tool runs. When overriding either method, include the
content you want the client to display. The default `Projection` implementation
provides both methods and can be subclassed when only part of the presentation
needs to change.