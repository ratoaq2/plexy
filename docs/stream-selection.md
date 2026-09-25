# Stream selection

plexy selects one audio stream and one subtitle stream (or no subtitle) for each media part. It writes the
selection to the Plex server. The code is in `plexy/api.py` (`VideoPart`).

## Watching preference

- `dubbed`: select the best audio stream for the desired language.
- `original`: select the best audio stream for the original language. The original language is the language
  of the default video stream. If it has no language, it is the language of the default audio stream.

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
4. The lower stream index.

When you change this order, add a test for the new case.
