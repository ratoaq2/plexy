# Typing

mypy checks `plexy` and `tests`. The settings are in `pyproject.toml`.

- Annotate every function: the parameters and the return type.
- Some libraries have no type stubs. The `[[tool.mypy.overrides]]` list in `pyproject.toml` names them.
  Their calls return `Any`. When you know the real type, use `typing.cast(...)`. Do not change the declared
  return type to `Any`.
- `plexy/api.py` uses `from __future__ import annotations`. Thus a class can refer to a class that the file
  defines later.
