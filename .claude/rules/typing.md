---
paths:
  - "plexy/**"
---

# Typing

Calls into libraries without stubs return `Any`. Use `typing.cast(...)` to the real type. Do not loosen the
declared return type. See `docs/typing.md`.
