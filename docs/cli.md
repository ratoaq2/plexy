# CLI

The CLI is in `plexy/cli.py`. It uses Click.

## Config files

The CLI reads the option defaults from config files, in this order. A later file overrides an earlier file:

1. `config.json`, `config.yml`, or `config.yaml` in the user config directory (`appdirs`).
2. `plexy.json`, `plexy.yml`, or `plexy.yaml` in the current directory.
3. The file of the `--config` option.

YAML needs the `yaml` extra (see `pyproject.toml`). `.gitignore` ignores local `plexy*.yml` files, because
they can contain a Plex token.

## Parameter types

| Type | Format | Example |
| --- | --- | --- |
| `LANGUAGE` | IETF language code | `pt-BR` |
| `AGE` | Numbers with the units `w`, `d`, and `h`, in this order | `1w2d` |
| `TITLE` | Name, then optional year, season, and episode. `Title.from_string` parses it. | `Game of Thrones (2011) s03e09` |
| Codec enums | A value of `AudioCodec` or `SubtitleCodec` in `plexy/api.py` | `truehd` |
