---
paths:
  - "tests/**"
---

# Tests

- Bug fix: commit a failing test that shows the bug first, then the fix. See `docs/workflow.md`.
- Run with quiet flags: `uv run pytest -q --tb=short tests`.
- Never connect to a real Plex server. Use the fake server (`fake_plex` fixture) and the fixtures in
  `tests/fixtures/`. See `docs/testing.md`.
- Never commit a media title, a path, or a real ID in a fixture. Read the fixture diff before the commit.
