# Changelog

## 0.3.1

- plexy now requires trakit 0.6.0. trakit now finds more forced streams: "Signs", "Foreign", and "S&S" in the stream title. It reads "LA" after Spanish as Latin America (`es-419`).

## 0.3.0

- Add support for Python 3.15.
- New tagline: "Your language, your way". `plexy --help` and the PyPI summary show it.
- New README for new users, with the common scenarios and a demo GIF. The full CLI reference is in `docs/usage.md`.
- Fix the stream rank when the desired language has no country or script. With `--language en`, plexy now selects a normal `en-US` subtitle before an `en` SDH subtitle. With `en-US` audio, plexy no longer selects subtitles. See "Rank of the streams" in `docs/stream-selection.md`.
- Fix the stream rank for forced and audio description streams. plexy now selects a full subtitle before a forced "Signs & Songs" subtitle in the same base language. plexy reads the `forced`, `hearingImpaired`, and `visualImpaired` flags from Plex, and the flag words in all the title fields. plexy now requires trakit 0.5.0.
- Add `--user` and the `user` configuration key. With the token of the server admin, plexy sets the preferences for this Plex user.
- Read the Plex token and the TMDB key from the env vars `PLEXY_TOKEN` and `PLEXY_TMDB_KEY`, or from a file with `PLEXY_TOKEN_FILE` and `PLEXY_TMDB_KEY_FILE`. Docker secrets use the `_FILE` method. See "Token and TMDB key" in `docs/usage.md`.
- Fix a `TypeError` in `preferences` with `--debug`.

## 0.2.2

- Fix `original` with a TMDB key when the media language has a country. TMDB gives `en` and the video is `en-US`: plexy now selects the `en-US` audio stream, not the `en` stream.

## 0.2.1

- The Docker image now reads YAML configuration files.
- Add the `--tmdb-key` option. With a TMDB key, `original` gets the original language from TMDB, not from the media file. plexy keeps the TMDB answers in a cache.
- Fix the stream rank when two streams have the same language but different countries. plexy now selects the stream with the desired country.
