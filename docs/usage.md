# Usage

This page is the reference for the plexy command line. For a first run, read the
[README](../README.md#quick-start).

## Commands

plexy has one command: `preferences`. The options of the `plexy` group (`--url`, `--token`, `--tmdb-key`,
`--user`, `--config`) come before the command name. The options of `preferences` come after it:

```bash
plexy --config friend.yml preferences --language de dubbed
```

`-t` is `--token` before `preferences`, and `--title` after it.

## Parameter formats

| Type | Format | Examples |
| --- | --- | --- |
| `LANGUAGE` | An IETF language code. | `en`, `pt-BR`, `zh-Hant` |
| `TITLE` | A name, then an optional year in parentheses, then an optional season (`s02`) or episode (`s03e09`). | `Avatar`, `The Matrix (1999)`, `The Boys s2`, `Chernobyl s01e03`, `Game of Thrones (2011) s03e09` |
| `AGE` | Numbers with the units `w` (weeks), `d` (days), and `h` (hours), in this order. | `12h`, `1w`, `1w2d` |
| Audio codec | A value in the `--audio-codec` list below. | `truehd`, `dca` |
| Subtitle codec | A value in the `--subtitle-codec` list below. | `pgs`, `eia_608` |

plexy sends the name to Plex as a title filter. Plex selects the titles that contain the name. For example,
`Matrix` selects all the Matrix movies. Add the year to select one movie: `The Matrix (1999)`.

The language rules (for example, why `en` also selects `en-US`) are in
[Stream selection](stream-selection.md).

## All options

```
$ plexy --help
Usage: plexy [OPTIONS] COMMAND [ARGS]...

  Your language, your way.

Options:
  -u, --url TEXT    Plex server address, e.g.: http://myserver:32400  [required]
  -t, --token TEXT  Plex token.  [required]
  --tmdb-key TEXT   TMDB read access token or API key. The original preference then gets the
                    original language from TMDB.
  --user TEXT       Plex user to set the preferences for: a username, an email, or a display name.
                    Needs the token of the server admin, or the Plex account token of this user.
  --config PATH     Path to the config file.
  --version         Show the version and exit.
  --help            Show this message and exit.

Commands:
  preferences  Your watching preferences

  Suggestions and bug reports: https://github.com/ratoaq2/plexy
```

```
$ plexy preferences --help
Usage: plexy preferences [OPTIONS] {original|dubbed}

  Your watching preferences

  Dubbed prefers an audio track with the desired language.
  Original prefers the original audio and an additional subtitle track if the audio is not in the desired language.

Options:
  -L, --library TEXT              Library to be used. e.g: Movies, Shows.
  -t, --title TITLE               Filter for titles in your library. It could refer to a movie, a
                                  show, a season or an episode. e.g: Avatar, The Matrix (1999),
                                  The Boys s2, Chernobyl s01e03, Game of Thrones (2011) s03e09
  -l, --language LANGUAGE         Desired watching language as IETF code, e.g.: en, pt-BR.
  -a, --audio-codec [dca|aac|opus|ac3|eac3|truehd|flac|mp2|mp3|vorbis|pcm|unknown]
                                  Accepted audio codec.
  -A, --excluded-audio-codec [dca|aac|opus|ac3|eac3|truehd|flac|mp2|mp3|vorbis|pcm|unknown]
                                  Excluded audio codec.
  -s, --subtitle-codec [srt|pgs|vobsub|ass|mov_text|eia_608|dvb_subtitle|unknown]
                                  Accepted subtitle codec.
  -S, --excluded-subtitle-codec [srt|pgs|vobsub|ass|mov_text|eia_608|dvb_subtitle|unknown]
                                  Excluded subtitle codec.
  -n, --newer-than AGE            Filter movies/episodes newer than AGE, e.g. 12h, 1w2d
  -o, --older-than AGE            Filter movies/episodes older than AGE, e.g. 12h, 1w2d
  -f, --full-summary              Print the full summary of changed preferences.
  --skip-watching                 Skip movies/episodes that watch is in progress.
  --keep-selected-audio           Do not change the selected audio. Useful when using original
                                  watching preference.
  --keep-selected-subtitle        Do not change the selected subtitle.
  --force-subtitles               Select subtitles, even when the audio already matches the
                                  desired language.
  --debug                         Print useful information for debugging and for reporting bugs.
  --help                          Show this message and exit.
```

You can use `--title`, `--library`, and the codec options more than one time.

## Configuration file

A configuration file gives the default value of each option. It is a YAML or a JSON file. YAML needs the
`yaml` extra: `uv tool install "plexy[yaml]"`.

- The keys are the option names, with `_` in place of `-`. For example, `--tmdb-key` is `tmdb_key`.
- The options of the `plexy` group go at the top: `url`, `token`, `tmdb_key`.
- The options of the `preferences` command go in the `preferences` section. The `{original|dubbed}` argument
  is `watching_preference`.
- An option with more than one value (for example `library`) is a list.

```yaml
url: http://myplexserver:32400
token: <your Plex token>
tmdb_key: <your TMDB read access token>
preferences:
  library:
    - Movies
    - TV Shows
  excluded_subtitle_codec:
    - eia_608
  full_summary: true
  language: pt-BR
  watching_preference: original
```

With this file, this command is sufficient:

```bash
plexy preferences
```

### File order

plexy reads the configuration files in this order:

1. `config.json`, `config.yml`, or `config.yaml` in the user configuration folder:
   - Linux: `~/.config/plexy/` (or `$XDG_CONFIG_HOME/plexy/`)
   - macOS: `~/Library/Application Support/plexy/`
   - Windows: `%LOCALAPPDATA%\plexy\plexy\`
2. `plexy.json`, `plexy.yml`, or `plexy.yaml` in the current folder.
3. The file of the `--config` option.

A later file replaces each top-level key of an earlier file. The `preferences` section of a later file
replaces all the `preferences` section of an earlier file. It does not merge them. An option on the command
line replaces the value of the configuration files.

### Token and TMDB key

The Plex token and the TMDB key are secrets. Do not keep them in a file in a project folder, a shared folder,
or a git repository. plexy takes each secret from the first source in this list:

1. The command line: `--token` or `--tmdb-key`. The shell history keeps the value.
2. The env var `PLEXY_TOKEN` or `PLEXY_TMDB_KEY`.
3. The env var `PLEXY_TOKEN_FILE` or `PLEXY_TMDB_KEY_FILE`: the path of a file that contains the secret.
   plexy removes the spaces and the line breaks at the start and at the end. Docker secrets use this method.
4. The `token` or `tmdb_key` key in a configuration file.

When you set `PLEXY_TOKEN` and `PLEXY_TOKEN_FILE` together, plexy stops with an error. The same rule applies to
`PLEXY_TMDB_KEY` and `PLEXY_TMDB_KEY_FILE`.

`PLEXY_TOKEN` and `PLEXY_TOKEN_FILE` replace the token of all configuration files. If you use one
configuration file for each Plex user, do not set them in your shell profile. Then each file gives its own
token.

With `--debug`, plexy shows the source of each secret, for example `Plex token from PLEXY_TOKEN`. It does not
show the value.

### More than one Plex user

plexy changes the tracks for one Plex user at a time. Without `--user`, this is the user of the token. There
are two methods to set the preferences of more than one user.

#### One configuration file for each user (recommended)

Each file contains the token of one user. Put the server address in a shared file:

```yaml
# plexy.yml in the current folder
url: http://myplexserver:32400
```

```yaml
# <path>/me.yml
token: <the token of the first user>
```

```yaml
# <path>/friend.yml
token: <the token of the second user>
```

```bash
plexy --config <path>/me.yml preferences --language pt-BR original
plexy --config <path>/friend.yml preferences --language de dubbed
```

Keep these files outside your project folders, for example in your user configuration folder.

Do not add the `user` key to these files. The token of a shared user or a managed user is often a server
token. plex.tv does not accept a server token, so plexy cannot check its owner. Then plexy stops with an
error.

#### One admin token for all users

With the token of the server admin, `--user` (or the `user` key) selects the user. Then the files do not
contain a token:

```yaml
# <path>/friend.yml
user: friend
preferences:
  language: de
  watching_preference: dubbed
```

```bash
export PLEXY_TOKEN_FILE=<path of the file with the admin token>
plexy --url http://myplexserver:32400 --config <path>/friend.yml preferences
```

#### How plexy uses `--user`

Give a username, an email, or a display name. The comparison ignores case. plexy asks plex.tv for the Plex
account of the token:

1. plex.tv does not accept the token: plexy stops with an error. plex.tv accepts only the token of a Plex
   account, not a server token. To use a server token, remove `--user` and the `user` key.
2. The account is the user of `--user`: plexy uses the token.
3. The account is the admin of the server: plexy gets a token for the user from plex.tv, and works as that
   user. If the user does not exist or has no access to the server, plexy stops with an error.
4. Else, plexy stops with an error, for example `The token belongs to neighbor, not to friend`.

With `--user`, plexy needs access to plex.tv. To work as another user with the admin token, the server must be
signed in to the Plex account of the admin.

## Original language from TMDB

With a TMDB key, `original` gets the original language of each movie and show from
[TMDB](https://www.themoviedb.org/). Without a key, plexy finds the original language in the media file. Some
files have a default track in a dubbed language. Then the result is not correct.

1. Make a free TMDB account.
2. Open [the API settings](https://www.themoviedb.org/settings/api) and request an API key.
3. Copy the **API Read Access Token**. The **API Key** also works, but it goes in the request URL.
4. Add it to your configuration file:

   ```yaml
   tmdb_key: <your TMDB read access token>
   ```

plexy sends one request for each movie and each show. It keeps the answers in a cache, so a later run sends
requests only for new titles. The rules are in [Stream selection](stream-selection.md#original-language-from-tmdb).

## Docker

The image [`ratoaq2/plexy`](https://hub.docker.com/r/ratoaq2/plexy) runs the `plexy` command. Give the token
as a Docker secret. Docker mounts the secret file in `/run/secrets/`, and `PLEXY_TOKEN_FILE` gives its path.
For example, with Docker Compose:

```yaml
services:
  plexy:
    image: ratoaq2/plexy
    command: --url http://myplexserver:32400 preferences --language pt-BR original
    environment:
      PLEXY_TOKEN_FILE: /run/secrets/plex_token
    secrets:
      - plex_token

secrets:
  plex_token:
    file: ./plex_token.txt
```

`plex_token.txt` contains only the token. For a TMDB key, add a second secret and `PLEXY_TMDB_KEY_FILE`.

The image also reads JSON and YAML configuration files. It starts in the `/` folder. Mount a file there, so
plexy finds it as `plexy.json` in the current folder. The file does not need a token:

```bash
docker run --rm -v "$PWD/plexy.json:/plexy.json" -e PLEXY_TOKEN_FILE=/run/secrets/plex_token \
  -v "$PWD/plex_token.txt:/run/secrets/plex_token:ro" ratoaq2/plexy preferences --language pt-BR original
```
