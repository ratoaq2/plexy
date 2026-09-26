# Changelog

## 0.2.1

- The Docker image now reads YAML configuration files.
- Add the `--tmdb-key` option. With a TMDB key, `original` gets the original language from TMDB, not from the media file. plexy keeps the TMDB answers in a cache.
- Fix the stream rank when two streams have the same language but different countries. plexy now selects the stream with the desired country.
