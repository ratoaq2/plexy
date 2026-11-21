<h1 align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/ratoaq2/plexy/main/docs/images/logo-dark.png">
    <img alt="plexy: Your language, your way" src="https://raw.githubusercontent.com/ratoaq2/plexy/main/docs/images/logo-light.png" width="400">
  </picture>
</h1>

Select the audio and subtitle tracks of your Plex movies and shows, in your language, with one command.

[![PyPI version](https://img.shields.io/pypi/v/plexy.svg)](https://pypi.org/project/plexy/)
[![Python versions](https://img.shields.io/pypi/pyversions/plexy.svg)](https://pypi.org/project/plexy/)
[![Tests](https://github.com/ratoaq2/plexy/actions/workflows/test.yml/badge.svg)](https://github.com/ratoaq2/plexy/actions/workflows/test.yml)
[![Docker pulls](https://img.shields.io/docker/pulls/ratoaq2/plexy.svg)](https://hub.docker.com/r/ratoaq2/plexy)
[![License](https://img.shields.io/github/license/ratoaq2/plexy.svg)](https://github.com/ratoaq2/plexy/blob/main/LICENSE)

![plexy selects the original audio with Brazilian Portuguese subtitles for one Plex user, and the German audio for a second user](https://raw.githubusercontent.com/ratoaq2/plexy/main/docs/images/demo.gif)

## Why plexy

Plex has no setting for "always play the original audio, with subtitles in my language". You must select the
audio and subtitle tracks for each movie and each episode. With a large library, this takes a long time.

plexy does it with one command, for all your libraries or for the titles that you select. You give a language
and a watching preference:

| Preference | Audio track | Subtitle track |
| --- | --- | --- |
| `original` | The original audio. | Your language, if the audio is not in your language. |
| `dubbed` | Your language. | Your language, only if no audio track is in your language. |

plexy gives a lower priority to:

- Commentary and audio description tracks.
- Forced subtitle tracks, for example "Signs & Songs".
- Closed caption (CC) and hearing-impaired (SDH) subtitle tracks.

> [!WARNING]
> plexy changes the track selection on your Plex server, for the Plex user of the token.
> Test it on one title first, with `--title` and `--full-summary`.

## Quick start

1. Install plexy:

   ```bash
   uv tool install "plexy[yaml]"
   ```

2. Get your Plex token. Follow the Plex article
   [Finding an authentication token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).
3. Make a file `plexy.yml` in the current folder, with your server address and your token:

   ```yaml
   url: http://myplexserver:32400
   token: <your Plex token>
   ```

4. Run plexy on one movie. This example selects the original audio, and English subtitles if the audio is not
   in English:

   ```text
   $ plexy preferences --language en --title "The Matrix (1999)" --full-summary original
   Configuring watching preferences  [####################################]  100%
   1 movie changed out of 1 selected movie
   The Matrix (1999) changed from pt-BR: Português (SRT External) to no subtitles
   ```

5. If the result is correct, run it on all your libraries:

   ```bash
   plexy preferences --language en original
   ```

## Installation

Use one of these commands:

| Command | When to use it |
| --- | --- |
| `uv tool install "plexy[yaml]"` | Recommended. [uv](https://docs.astral.sh/uv/getting-started/installation/) also installs Python if necessary. |
| `pipx install "plexy[yaml]"` | You already use [pipx](https://pipx.pypa.io/). |

The `yaml` extra is necessary only for a YAML configuration file. A JSON file works without it. The supported
Python versions are in [`pyproject.toml`](pyproject.toml).

To upgrade, use `uv tool upgrade plexy` or `pipx upgrade plexy`.

For Docker, see [Docker](docs/usage.md#docker).

## Usage

The examples use the configuration file from [Quick start](#quick-start).

Only one movie, French subtitles with the original audio:

```bash
plexy preferences --language fr --title "The Matrix (1999)" original
```

A show, a season, or an episode, German audio:

```bash
plexy preferences --language de --title "Game of Thrones" dubbed
plexy preferences --language de --title "The Mandalorian s02" dubbed
plexy preferences --language de --title "Game of Thrones s03e09" dubbed
```

Only the "Movies" library, English audio:

```bash
plexy preferences --library Movies --language en dubbed
```

The titles that you added in the last week:

```bash
plexy preferences --language pt-BR --newer-than 1w original
```

Do not select an audio codec that your player cannot play. For example, the Chromecast with Google TV cannot
play Dolby TrueHD:

```bash
plexy preferences --language pt-BR --excluded-audio-codec truehd original
```

Change only the subtitles, and keep the audio that you selected:

```bash
plexy preferences --language pt-BR --keep-selected-audio original
```

Select subtitles also when the audio is in your language:

```bash
plexy preferences --language en --force-subtitles dubbed
```

Two Plex users with different preferences. The token selects the user, so each user has a configuration file
with a token (see [More than one Plex user](docs/usage.md#more-than-one-plex-user)):

```bash
plexy --config me.yml preferences --language pt-BR original
plexy --config friend.yml preferences --language de dubbed
```

### Main options

These are the options of `plexy preferences`. The last argument is the watching preference: `original` or
`dubbed`.

| Option | What it does |
| --- | --- |
| `-l`, `--language` | Your language, for example `en` or `pt-BR`. |
| `-t`, `--title` | Only this movie, show, season, or episode, for example `The Matrix (1999)` or `The Boys s2`. You can use it more than one time. |
| `-L`, `--library` | Only this library, for example `Movies`. You can use it more than one time. |
| `-n`, `--newer-than` | Only the titles added in this time, for example `12h` or `1w2d`. |
| `-o`, `--older-than` | Only the titles added before this time, for example `1w`. |
| `-A`, `--excluded-audio-codec` | Do not select an audio track with this codec, for example `truehd`. |
| `-S`, `--excluded-subtitle-codec` | Do not select a subtitle track with this codec, for example `eia_608`. |
| `-f`, `--full-summary` | Show each change. |
| `--skip-watching` | Do not change a title that you started to watch and did not finish. |
| `--keep-selected-audio` | Do not change the audio track. |
| `--keep-selected-subtitle` | Do not change the subtitle track. |
| `--force-subtitles` | Select subtitles also when the audio is in your language. |
| `--debug` | Show information to report a bug. |

Before `preferences`, `--url`, `--token`, and `--tmdb-key` connect plexy to your server and to TMDB.
`--config` gives a configuration file. For all options and their formats, see [docs/usage.md](docs/usage.md).

### Configuration file

A configuration file can contain all the options. Put the options of `plexy preferences` in the
`preferences` section, with `_` in place of `-`:

```yaml
url: http://myplexserver:32400
token: <your Plex token>
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

plexy reads a file in your user configuration folder, `plexy.yml` in the current folder, and the file of the
`--config` option. An option on the command line replaces the value in the file. For the order and the
folders, see [Configuration file](docs/usage.md#configuration-file).

### Original language from TMDB

For `original`, plexy finds the original language in the media file: the language of the default video track,
or else of the default audio track. Some files have a default track in a dubbed language. For a better
result, add a free [TMDB](https://www.themoviedb.org/) key to your configuration file:

```yaml
tmdb_key: <your TMDB read access token>
```

To get a key, see [Original language from TMDB](docs/usage.md#original-language-from-tmdb).

## FAQ

**Which track does plexy select when many tracks are in my language?**
plexy sorts the tracks with rules, for example a normal track before an SDH track. See
[Stream selection](docs/stream-selection.md).

**Why did plexy remove my subtitles?**
plexy removes the subtitles when the audio is in your language. To keep subtitles, use `--force-subtitles`.

**Does plexy change the tracks for all the users of my Plex server?**
No. It changes them only for the Plex user of the token. For a second user, use the token of that user. See
[More than one Plex user](docs/usage.md#more-than-one-plex-user).

**Does plexy change my media files?**
No. It changes only the track selection on the Plex server.

**How do I go back to the old tracks?**
plexy does not keep the old selection. Run plexy again with other options, or select the tracks in Plex.

**plexy says "No video found". Why?**
No title matches your filters. Check the name of the title and the library. When `--title` has a year, it
must be the year in Plex.

## Report a bug

Open an [issue](https://github.com/ratoaq2/plexy/issues). Add the output of the command with the `--debug`
option. Before you send the output, make sure that it does not contain your Plex token or your TMDB key.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).

The plexy name, logo, and icon are not covered by the MIT license. All rights reserved.
