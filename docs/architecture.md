# Architecture

One line for each module in `plexy/`.

| Module | Role |
| --- | --- |
| `plexy/__init__.py` | Package metadata (title, version, URL) and the public API that `plexy/cli.py` imports. |
| `plexy/__main__.py` | Entry point for `python -m plexy`. |
| `plexy/api.py` | Domain logic. `Plex` connects to the server and searches. `Criteria` holds the search filters. `Title` parses a title filter. `Video` and `VideoPart` are a matched movie or episode and its media parts. `Stream` is an audio or subtitle stream, with the language, commentary, and hearing-impaired flags that `trakit` guesses. `Preferences` holds the user preferences. `Change` records what changed on a part. |
| `plexy/cli.py` | Click CLI: the `plexy` group, the `preferences` command, the custom parameter types, and the config file loading. See `docs/cli.md`. |
| `plexy/utils.py` | Helpers: the display title of a stream, and the languages that the Plex fields of a stream give. |
| `plexy/exceptions.py` | `Error` is the base class. `InvalidTitle` is the only subclass. `Title.from_string` raises it. |
