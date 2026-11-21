# CLI

The CLI is in `plexy/cli.py`. It uses Click. To run it from the repo:

```
uv run plexy --url <PLEX_URL> --token <TOKEN> preferences ...
```

The user reference (all options, parameter formats, configuration files and their order) is in
`docs/usage.md`.

## Config files

`set_default_config` reads the config files into the Click `default_map`. It uses a shallow `dict.update`, so a
later file replaces each top-level key, for example all of `preferences`. The user config directory comes
from `appdirs`.

The `plexy` group has `--url`, `--token`, and `--tmdb-key`. The config keys are `url`, `token`, and
`tmdb_key`. The `preferences` command writes its cache to the user cache directory (`appdirs`).

YAML needs the `yaml` extra (see `pyproject.toml`). `.gitignore` ignores local `plexy*.yml` files, because
they can contain a Plex token or a TMDB key.

## Parameter types

`LanguageParamType`, `AgeParamType`, `TitleParamType`, and `EnumParamType` in `plexy/cli.py` parse the
parameters. `Title.from_string` parses a title. The codec values are `AudioCodec` and `SubtitleCodec` in
`plexy/api.py`.
