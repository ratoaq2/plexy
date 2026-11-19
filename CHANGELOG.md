# Changelog

## Unreleased

- Add support for Python 3.15.
- Fix the stream rank when the desired language has no country or script. With `--language en`, plexy now selects a normal `en-US` subtitle before an `en` SDH subtitle. With `en-US` audio, plexy no longer selects subtitles. See "Rank of the streams" in `docs/stream-selection.md`.
- Fix the stream rank for forced and audio description streams. plexy now selects a full subtitle before a forced "Signs & Songs" subtitle in the same base language. plexy reads the `forced`, `hearingImpaired`, and `visualImpaired` flags from Plex, and the flag words in all the title fields. plexy now requires trakit 0.5.0.

## 0.2.2

- Fix `original` with a TMDB key when the media language has a country. TMDB gives `en` and the video is `en-US`: plexy now selects the `en-US` audio stream, not the `en` stream.

## 0.2.1

- The Docker image now reads YAML configuration files.
- Add the `--tmdb-key` option. With a TMDB key, `original` gets the original language from TMDB, not from the media file. plexy keeps the TMDB answers in a cache.
- Fix the stream rank when two streams have the same language but different countries. plexy now selects the stream with the desired country.
