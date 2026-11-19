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
3. If the language of the selected audio does not match the desired language (see "Rank of the streams"),
   or the user forces subtitles, select
   the best subtitle stream for the desired language. Otherwise, remove the subtitle selection.

The "keep selected" options keep the current audio or subtitle selection.

## Rank of the streams

plexy sorts the streams by rank and selects the first. The code is `VideoPart.__get_lang_key`.

### Terms

- **Target**: the language that plexy looks for. For subtitles and for `dubbed` audio, it is `--language`.
  For `original` audio, it is the original language.
- **Parts of a language**: a base language (`alpha3`), and an optional script and country. `en` has only a
  base language. `pt-BR` has a country. `zh-Hant` has a script. `zh-TW-Hant` has both.
- **Match**: a stream matches the target when each part that the target has is the same in the stream. A part
  that the target does not have has no effect. The target `en` matches `en`, `en-US`, and `en-GB`. The target
  `pt-BR` matches only `pt-BR`. The target `zh-TW-Hant` does not match `zh-TW`, because `zh-TW` has no script.
- **Flagged stream**: a commentary, closed-caption, or hearing-impaired (SDH) stream. A normal stream has no
  flag.
- **External stream**: a subtitle file next to the media file. An embedded stream is in the media file.

### Groups

The groups, from best to worst:

1. Normal streams that match the target.
2. Flagged streams that match the target.
3. Streams with the same base language that do not match the target, in this order:
   1. Same script as the target, other country.
   2. Other script, same country as the target.
   3. Other script and other country.

   A part that the target does not have counts as the same. For example, with the target `pt-BR`, `pt` and
   `pt-PT` both have the same script.
4. Streams in another base language.

### Order in a group

In each group, and in each step of group 3, plexy uses these rules in this order:

1. A normal stream comes first. Then an SDH stream, then a closed-caption stream, then a commentary stream.
2. A stream in the exact target language comes first. With the target `fr`, `fr` comes before `fr-CA`.
3. An embedded stream comes before an external stream.
4. The stream with the lower index comes first.

### Examples

| Target | Streams | Selected | Why |
| --- | --- | --- | --- |
| `en` | `en-US` normal, `en` SDH | `en-US` normal | Both match. A normal stream comes before an SDH stream. |
| `en` | `en-US` normal, `en` normal | `en` normal | Both match and are normal. `en` is the exact target. |
| `pt-BR` | `pt-BR` SDH, `pt` normal | `pt-BR` SDH | Only `pt-BR` matches. A match comes first, also when it has a flag. |
| `zh-Hant` | `zh-Hant` SDH, `zh-Hans` normal | `zh-Hant` SDH | Only `zh-Hant` matches. A match comes first, also when it has a flag. |
| `en-US` | `en-US` SDH, `en-GB` normal | `en-US` SDH | Only `en-US` matches. A match comes first, also when it has a flag. |
| `zh-TW-Hant` | `zh-CN` normal, `zh-TW` normal | `zh-TW` normal | No stream matches. `zh-TW` has the same country as the target. |
| `pt-BR` | `pt-BR` external, `pt-BR` embedded | `pt-BR` embedded | Both match and are normal. An embedded stream comes first. |

What the user types decides first. A flag decides only between streams in the same group.

Limit: with `en`, the country of the stream has no effect. Between `en-US` and `en-GB`, the lower index wins.
To get `en-US` first, type `en-US`. Then an `en-US` SDH stream comes before an `en-GB` normal stream.

### Audio in the desired language

`save_preferences` uses the same rule for the subtitle step (see "Audio and subtitle", step 3). The audio is
in the desired language when its language matches the target. With the target `en`, `en-US` audio matches.
plexy then removes the subtitle selection, unless the user forces subtitles.

When you change this order, add a test for the new case in `tests/test_rank.py`.
