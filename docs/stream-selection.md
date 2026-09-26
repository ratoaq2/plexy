# Stream selection

plexy selects one audio stream and one subtitle stream (or no subtitle) for each media part. It writes the
selection to the Plex server. The code is in `plexy/api.py` (`VideoPart`).

## Watching preference

- `dubbed`: select the best audio stream for the desired language.
- `original`: select the best audio stream for the original language. plexy finds the original language in
  this order:
  1. TMDB, when the user gives a TMDB key and an audio stream has the TMDB language (see below).
  2. The language of the default video stream.
  3. The language of the default audio stream.

  TMDB gives only the base language, with no country. When the language of step 2 or 3 has the same base
  language, plexy uses it. For example, TMDB gives `en` and the video stream is `en-US`: the target is `en-US`.

## Original language from TMDB

`plexy/original_language.py` has `OriginalLanguages`. It finds the `tmdb://` guid of the movie, or of the
show of an episode. Then it gets `original_language` from the TMDB API.

- The key of each answer is the Plex guid of the movie or show. The answers go to
  `original_languages.jsonl` in the user cache directory (`appdirs`). A later run sends no request for them.
- One request for each movie and each show. Episodes of one show use one answer.
- A read access token goes in the `Authorization` header. A v3 API key goes in the URL, so plexy never logs
  the URL or the text of a request error.
- On `429`, the session waits (`Retry-After`) and sends the request again, at most 5 times.
- A `404` skips that title. Other errors stop TMDB for the rest of the run. Errors do not go to the cache.
- TMDB codes that are not ISO 639-1 (`xx`, `cn`) give no language. Then plexy uses the media streams.

## Audio and subtitle

1. Remove the streams that the codec options exclude. If the user gives codecs, keep only those codecs.
2. Sort the other streams by rank (see below). Select the first. If no stream is left, keep the current
   selection.
3. If the language of the selected audio is not the desired language, or the user forces subtitles, select
   the best subtitle stream for the desired language. Otherwise, remove the subtitle selection.

The "keep selected" options keep the current audio or subtitle selection.

## Rank of the streams

`VideoPart.__get_lang_cmp` compares two streams. The better stream comes first:

1. A stream in the exact target language.
2. A stream with the same base language (`alpha3`). Then the same script, or the same country.
3. For two streams in the same language: a normal stream before a commentary stream, a closed-caption
   stream, or a hearing-impaired (SDH) stream.
4. The lower stream index. Two streams with the same language and the same flags keep the Plex order.

When you change this order, add a test for the new case in `tests/test_rank.py`.
