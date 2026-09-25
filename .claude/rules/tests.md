---
paths:
  - "tests/**"
---

# Tests

- Bug fix: commit a failing test that shows the bug first, then the fix. See `docs/workflow.md`.
- Run with quiet flags: `uv run pytest -q --tb=short tests`.
- Never connect to a real Plex server. Mock the plexapi objects with mockito (`mock(values, spec=...)`).
