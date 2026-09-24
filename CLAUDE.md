# plexy

CLI tool that sets Plex watching preferences (audio/subtitle track selection) via the Plex API.

## Commands

Package management is via [uv](https://docs.astral.sh/uv/), not pip/poetry.

- Install deps: `uv sync --all-extras`
- Run everything CI runs: `uv run bash scripts/test.sh` (ruff check, ruff format --check, mypy, pytest)
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`
- Type-check: `uv run mypy plexy tests`
- Test: `uv run pytest plexy tests -vv`
- Run the CLI locally: `uv run plexy --url <PLEX_URL> --token <TOKEN> preferences ...`
- Build: `uv build`

Pre-commit hooks (ruff + mypy) are configured in `.pre-commit-config.yaml`; run `uv run pre-commit install` once per clone.

## Code style

- Line length 120, enforced by Ruff (lint rules: `E, F, W, I, UP, B`; formatter is Ruff's black-compatible formatter).
- Every function/method needs a full type annotation (params + return) — mypy runs with
  `disallow_untyped_defs`, `disallow_incomplete_defs`, `check_untyped_defs`, `warn_return_any` enabled
  (not full `--strict`). `plexy/api.py` uses `from __future__ import annotations` for forward references
  between classes defined later in the file.
- Third-party libraries without type stubs (`babelfish`, `plexapi`, `trakit`, `mockito`) are
  `ignore_missing_imports`d in `[tool.mypy]`; when a call into one of them returns `Any` but the real
  runtime type is known, use `typing.cast(...)` rather than loosening the function's declared return type.
- No docstrings unless behavior is genuinely non-obvious — matches existing code.

## Project map

- `plexy/api.py` — core domain logic: `Plex` (server connection + search), `Criteria` (search
  filters), `Video`/`VideoPart` (a matched movie/episode and its media parts), `Stream` (an audio or
  subtitle stream, with guessed language/commentary/hearing-impaired metadata via `trakit`),
  `Preferences` (user's dubbed/original + codec preferences), `Change` (a record of what got changed
  on a given part).
- `plexy/cli.py` — Click CLI: the `plexy` group and `preferences` command, plus custom
  `click.ParamType`s (`LANGUAGE`, `AGE`, `TITLE`, codec enums) and config-file loading
  (`config.{json,yml,yaml}` in the user config dir, then `plexy.{json,yml,yaml}` in the cwd, then
  `--config` overrides both).
- `plexy/utils.py` — helpers for picking a stream's display title and guessing its language(s)
  from Plex's `languageCode`/`language`/`languageTag` fields.
- `plexy/exceptions.py` — `Error` base class; `InvalidTitle` is the only subclass (raised by
  `Title.from_string`).

## Domain terms

- **Watching preference**: `dubbed` (prefer an audio track in the desired language) vs. `original`
  (prefer the original/default audio track, plus a subtitle track in the desired language if needed).
- **Title filter**: parsed by `Title.from_string` into name/year/season/episode, e.g.
  `"Game of Thrones (2011) s03e09"`.
- Stream selection priority: commentary tracks and closed-caption/SDH subtitle tracks rank lower
  than "normal" tracks in the same language (see `VideoPart._VideoPart__get_lang_cmp`).
