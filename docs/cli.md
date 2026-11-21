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

## Secrets

`SECRET_ENVVARS` in `plexy/cli.py` maps the secret config keys (`token`, `tmdb_key`) to their env vars. Click
reads the env var with `envvar=`, and puts it before the `default_map`. `set_default_config` reads the file
of `<env var>_FILE` into the `default_map`, after the config files. So the order is: command line, env var,
file, config file. `docs/usage.md` gives the order for users.

`secret_source` gets the source of each secret from `ctx.get_parameter_source`. `Settings` keeps it, and
`Plex` writes it to the debug log. Never log the value of a secret.

YAML needs the `yaml` extra (see `pyproject.toml`). Local `plexy*.{yml,yaml,json}` files can contain a Plex
token or a TMDB key. `.gitignore` ignores them, a pre-commit hook blocks them, and `.claude/settings.json`
denies Claude Code reads of them. The shell deny rules are best-effort.

## Parameter types

`LanguageParamType`, `AgeParamType`, `TitleParamType`, and `EnumParamType` in `plexy/cli.py` parse the
parameters. `Title.from_string` parses a title. The codec values are `AudioCodec` and `SubtitleCodec` in
`plexy/api.py`.
