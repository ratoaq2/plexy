# Plexy

[![Latest Version](https://img.shields.io/pypi/v/plexy.svg)](https://pypi.python.org/pypi/plexy)
[![tests](https://github.com/ratoaq2/plexy/actions/workflows/test.yml/badge.svg)](https://github.com/ratoaq2/plexy/actions/workflows/test.yml)
[![License](https://img.shields.io/github/license/ratoaq2/plexy.svg)](https://github.com/ratoaq2/plexy/blob/main/LICENSE)

Plexy is a command line tool. It selects the audio and subtitle tracks for your Plex movies and shows, in the language that you want.

```bash
plexy preferences --language en --title "The Matrix (1999)" --full-summary original
```
```
Configuring watching preferences  [####################################]  100%
1 movie changed out of 1 selected movie
The Matrix (1999) changed from pt-BR: Português (SRT External) to no subtitles
```

## Why

Plex does not have one setting for "always play the original audio with subtitles in my language".
You must select the audio and subtitle tracks for each movie or show.
With a large library, this takes a long time.
Plexy does it for all your library, or for the titles that you select, with one command.

## How it works

You give a language and a watching preference: `original` or `dubbed`.

| Preference | Audio track | Subtitle track |
| --- | --- | --- |
| `original` | The original audio. | Your language, if the audio is not in your language. |
| `dubbed` | Your language. | Your language, only if no audio track is in your language. |

Plexy gives a lower priority to:

- Commentary audio tracks.
- Closed caption (CC) and hearing-impaired (SDH) subtitle tracks.

> [!WARNING]
> Plexy changes the track selection on your Plex server, for the Plex user of the token.
> Test it on one title first, with `--title` and `--full-summary`.

## Install

Plexy needs Python. The supported versions are in [`pyproject.toml`](pyproject.toml).

With [uv](https://docs.astral.sh/uv/) (recommended):

```bash
uv tool install "plexy[yaml]"
```

Or with [pipx](https://pipx.pypa.io/):

```bash
pipx install "plexy[yaml]"
```

The `yaml` extra is necessary only for a YAML configuration file. A JSON file works without it.

With Docker, see [Use Docker](#use-docker).

## Quick start

1. Get your Plex token. Follow the Plex article
   [Finding an authentication token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).
2. Make a file `plexy.yml` in the current folder, with your server address and your token:

   ```yaml
   url: http://myplexserver:32400
   token: ABCDEFGHIJ1234567890
   ```

3. Run plexy on one movie first:

   ```bash
   plexy preferences --language pt-BR --title "The Matrix (1999)" --full-summary original
   ```

4. If the result is correct, run it on all your libraries:

   ```bash
   plexy preferences --language pt-BR original
   ```

You can also give the server address and the token on the command line:

```bash
plexy --url http://myplexserver:32400 --token ABCDEFGHIJ1234567890 preferences --language pt-BR original
```

## Examples

The examples use the configuration file from [Quick start](#quick-start).

### Select titles

Only Game of Thrones, French subtitles with the original audio:

```bash
plexy preferences --language fr --title "Game of Thrones" original
```

Only The Mandalorian, season 2, German audio:

```bash
plexy preferences --language de --title "Mandalorian s02" dubbed
```

Only Game of Thrones, season 3, episode 9, German audio:

```bash
plexy preferences --language de --title "Game of Thrones s03e09" dubbed
```

All Matrix movies and the first Avatar movie, Spanish audio:

```bash
plexy preferences --language es --title "Matrix" --title "Avatar (2009)" dubbed
```

### Select a library

Only the "Movies" library, English audio:

```bash
plexy preferences --library Movies --language en dubbed
```

### Select by date added

Titles added in the last week:

```bash
plexy preferences --language pt --newer-than 1w original
```

Titles in the "Movies" library, added before the last week:

```bash
plexy preferences --library Movies --language pt-BR --older-than 1w original
```

### Exclude a codec

Some players cannot play all codecs. For example, the Chromecast with Google TV cannot play Dolby TrueHD audio.
This command does not select TrueHD audio tracks:

```bash
plexy preferences --language pt-BR --excluded-audio-codec truehd original
```

## Configuration file

A configuration file can contain all the options. Put the options of the `preferences` command under `preferences`:

```yaml
url: http://myplexserver:32400
token: ABCDEFGHIJ1234567890
preferences:
  library:
    - Movies
    - TV Shows
  excluded_subtitle_codec:
    - eia_608
  full_summary: True
  language: pt-BR
  watching_preference: original
```

With this file, this command is sufficient:

```bash
plexy preferences
```

Plexy reads the configuration files in this order. A later file overrides an earlier file.

1. `config.json`, `config.yaml`, or `config.yml` in the user folder:
   - macOS: `~/Library/Preferences/plexy`
   - Linux: `~/.config/plexy/`
   - Windows: `C:\Users\<USER>\AppData\Local\plexy\plexy`
2. `plexy.json`, `plexy.yaml`, or `plexy.yml` in the current folder.
3. The file of the `--config` option:

   ```bash
   plexy --config myconfig.yml preferences
   ```

Options on the command line override the configuration files.

## Use Docker

The Docker image does not read YAML files. Use a JSON configuration file, for example `plexy.json`:

```json
{
  "url": "http://myplexserver:32400",
  "token": "ABCDEFGHIJ1234567890"
}
```

Then run:

```bash
docker run --rm -v "$PWD/plexy.json:/plexy.json" ratoaq2/plexy preferences --language pt-BR original
```

## All options

<details>
<summary><code>plexy preferences --help</code></summary>

```
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

</details>

## Report a bug

Open an [issue](https://github.com/ratoaq2/plexy/issues). Add the output of the command with the `--debug` option.
Before you send the output, make sure that it does not contain your token.

## Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT. See [LICENSE](LICENSE).
