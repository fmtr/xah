# Customize a tool by subclassing

This exercise builds on the age lookup by introducing a second kind of response while reusing the existing tool's foundation. It shows how to adapt an example for a new purpose without repeating its setup.

```python
--8<-- "xah/examples/m02/e04_subclassing.py"
```

1. Because `PetTool` uses the same user argument as `AgeTool`, subclassing reuses its definition instead of duplicating it.
2. Override `run()` to change the behavior while retaining the inherited argument.

The next exercise launches a harness that uses this subclass.