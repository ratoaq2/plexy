# Plexy
Your Plex, your way

[![Latest
Version](https://img.shields.io/pypi/v/plexy.svg)](https://pypi.python.org/pypi/plexy)

[![tests](https://github.com/ratoaq2/plexy/actions/workflows/test.yml/badge.svg)](https://github.com/ratoaq2/plexy/actions/workflows/test.yml)

[![License](https://img.shields.io/github/license/ratoaq2/plexy.svg)](https://github.com/ratoaq2/plexy/blob/master/LICENSE)

  - Project page  
    <https://github.com/ratoaq2/plexy>

## Info

**Plexy** is a command line tool to save your watching preferences in Plex.

**Dubbed** or **Original audio**, it's up to you.

- For **Dubbed** preference, Plexy will auto-select the audio track with your desired language.
If no audio track is found, Plexy will auto-select the subtitle track with your desired language.
- For **Original** preference, Plexy will auto-select the default/original audio track 
and the subtitle track in your desired language.

Priorities:
- Commentary audio tracks have lower priority when selecting audio tracks
- Closed caption and SDH subtitle tracks also have lower priority when selecting subtitles


To select Brazilian Portuguese language with original audio
```bash
>> plexy --url http://mylocalplex:32400 --token ABCDEF1234567890 preferences --language pt-BR original
```

To select English language with dubbed audio
```bash
>> plexy --url http://mylocalplex:32400 --token ABCDEF1234567890 preferences --language en dubbed
```

To select French language with original audio only for Game of Thrones
```bash
>> plexy --url http://mylocalplex:32400 --token ABCDEF1234567890 preferences --language fr --title "Game of Thrones" original
```

To select German language with dubbed audio only for Mandalorian Season 2
```bash
>> plexy --url http://mylocalplex:32400 --token ABCDEF1234567890 preferences --language fr --title "Mandalorian s02" dubbed
```

To select German language with dubbed audio only for Game of Thrones, season 3 and episode 9
```bash
>> plexy --url http://mylocalplex:32400 --token ABCDEF1234567890 preferences --language fr --title "Game of Thrones s03e09" dubbed
```

To select Spanish language with dubbed audio only for all Matrix movies and the first Avatar movie
```bash
>> plexy --url http://mylocalplex:32400 --token ABCDEF1234567890 preferences --language es --title "Matrix" --title "Avatar (2009)" dubbed
```

To select Portuguese language with original audio for everything added to your libraries in the last week
```bash
>> plexy --url http://mylocalplex:32400 --token ABCDEF1234567890 preferences --language pt --newer 1w original
```

To select Brazilian Portuguese language with original audio for everything added to your "Movie" library before the last week
```bash
>> plexy --url http://mylocalplex:32400 --token ABCDEF1234567890 preferences --library Movie --language pt-BR --older 1w original
```

You can also select or exclude tracks based on their codec/format.
For instance, you have a Chromecast with Google TV which doesn't support Dolby TrueHD audio codec.
You can exclude this codec when saving your preferences: 
```bash
>> plexy --url http://mylocalplex:32400 --token ABCDEF1234567890 preferences --language pt-BR -A truehd original
```

And print the full summary of changes:
```bash
>> plexy --url http://mylocalplex:32400 --token ABCDEFGHIJ1234567890 preferences -f -l en --title "The Matrix (1999)" original
Configuring watching preferences  [####################################]  100%
1 movie changed out of 1 selected movie
The Matrix (1999) changed from pt-BR: Português (SRT External) to no subtitles
```


You can also define your configuration options in a `json` or `yaml` file:
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

By default, plexy will load `config.json`, `config.yaml` or `config.yml` file from the folders:
- Mac OS: `~/Library/Preferences/plexy`
- Linux: `~/.config/plexy/`
- Windows: `C:\Users\<USER>\AppData\Local\plexy\plexy`

And then update the configuration with data from `plexy.json`, `plexy.yaml` or `plexy.yml` in the current working directory.

You can pass the configuration to use with the `--config` parameter:
```bash
>> plexy --config myconfig.yml preferences
Configuring watching preferences  [####################################]  100%
1 movie changed out of 1 selected movie
The Matrix (1999) changed from pt-BR: Português (SRT External) to no subtitles
```


All available CLI options:
```bash
>> plexy --url <PLEX_URL> --token <USER_TOKEN> preferences --help
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
  -a, --audio-codec [dca|aac|ac3|eac3|truehd|flac|mp2|mp3|vorbis|pcm]
                                  Accepted audio codec.
  -A, --excluded-audio-codec [dca|aac|ac3|eac3|truehd|flac|mp2|mp3|vorbis|pcm]
                                  Excluded audio codec.
  -s, --subtitle-codec [srt|pgs|vobsub|ass|mov_text|eia_608|dvb_subtitle]
                                  Accepted subtitle codec.
  -S, --excluded-subtitle-codec [srt|pgs|vobsub|ass|mov_text|eia_608|dvb_subtitle]
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


## Using Docker


    docker run -it --rm plexy --url http://mylocalplex:32400 --token ABCDEF1234567890 preferences --language pt-BR -A truehd original


## Installation

**Plexy** can be installed as a regular python module by running:

    $ [sudo] pip install plexy

For a better isolation with your system you should use a dedicated
virtualenv or install for your user only using the `--user` flag.

## Dependencies
* [Diaoul/babelfish](https://github.com/Diaoul/babelfish)
* [pkkid/python-plexapi](https://github.com/pkkid/python-plexapi)
* [ratoaq2/trakit](https://github.com/ratoaq2/trakit)
