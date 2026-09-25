# Testing

Tests never connect to a real Plex server. They run the real plexy and plexapi code on Plex XML that a fake
server gives.

## Fake server

`tests/fakeplex.py` has `FakePlex`, a `requests.Session` that acts as a Plex server. The `fake_plex` fixture
in `tests/conftest.py` loads a scenario and makes each `PlexServer` use `FakePlex` as its session. Then
`Plex`, `Video`, and the CLI run with no network and no change to `plexy/`.

```python
def test_example(fake_plex: FakePlexFactory) -> None:
    fake = fake_plex("movie_1")
    run(Criteria(), preferences(WatchingPreference.ORIGINAL, "en"))
    assert fake.puts == [Request("/library/parts/1", {"allParts": "1", "subtitleStreamID": "0"})]
```

- `fake.gets` and `fake.puts` record each request: the path and the parameters.
- A PUT that selects a stream changes the fake data. A second run sees the new selection.
- The fake does not apply the search filters. A search gives all the items of that section and type. Tests
  check the filters that plexy sends (`fake.searches`). Plex decides what a filter means.
- When plexy searches the same section and type two times in one run, the fake fails the test, because the
  results would repeat. Give the result of each search with `fake.answer({"title": "Movie 1"}, [1])`.
- A request that the fake does not know fails the test. This shows a new request from plexy or plexapi.

## CLI tests

The CLI reads config files from the current folder and the user config folder (see `docs/cli.md`). The
`invoke` fixture in `tests/test_cli.py` runs the CLI in an empty temporary folder, with an empty user config
folder. Then a local `plexy.yml` does not change the result.

## Fixtures

`tests/fixtures/` has:

- `server/`: the shared server responses. The section ID in them is `SECTION`. The fake replaces it.
- `<scenario>/sections.xml` and `<scenario>/metadata/<ratingKey>.xml`: a small library. Put only the items
  that the tests of the scenario need.

## Builder

`tests/builders.py` makes small Plex XML in the test: `video`, `part`, `audio`, `subtitle`, and
`video_stream`. Use it for a rule of the stream selection. Use a fixture for a case from a real library.

```python
elem = video(part(audio("ja", 1, selected=True), audio("en", 2), subtitle("en", 3)))
```

- `media_part(elem)` gives a plexapi `MediaPart` with no server. `tests/test_rank.py` uses it with
  `VideoPart.choose_audio_track` and `VideoPart.choose_subtitle_track`.
- `fake_plex(items=[elem])` puts the video on the fake server. It copies the video, so a PUT does not
  change `elem`. Use it when the test checks `fake.puts`.
- The stream ID is the stream index + 1.

## Capture tool

`scripts/capture_fixture.py` reads items from a real Plex server and writes them as a scenario. It sends GET
requests only. Any other request raises an error before it goes to the server.

```
uv run python scripts/capture_fixture.py --config plexy.yml --config plexy-user.yml --title "Some Show s01e03" --scenario episode_2
uv run python scripts/capture_fixture.py --config plexy.yml --config plexy-user.yml --rating-key 1234 --scenario movie_2
uv run python scripts/capture_fixture.py --config plexy.yml --config plexy-user.yml --server
```

- `--config` takes the CLI config files (see `docs/cli.md`). A later file overrides an earlier file. They
  must give `url` and `token`.
- `--title` works as the `--title` option of the CLI. `--library` limits the search.
- `--scenario` writes one full scenario. Give all its items in one command. Use `--force` to replace it.
- `--server` writes `tests/fixtures/server/` again.

## Private data

Fixtures go to a public repo. Media titles, paths, and the size of the library must never go into a
fixture. The tool:

- keeps an allowlist of XML elements and attributes,
- renames media titles (`Movie 1`, `Show 1`, `Episode 1`) and library names (`Movies`, `Shows`),
- renumbers all IDs from 1, because real IDs show the size of the library,
- sets counts (`size`, `totalSize`) from the fixture, not from the server,
- removes the server name, the user name, and the machine identifier,
- replaces each stream title word that trakit and babelfish do not know with `word1`, `word2`, and prints a
  warning.

Stream languages, codecs, and flag words (`SDH`, `Forced`, `Commentary`) stay, because plexy needs them. The
tool compares the language and flags that plexy finds for each stream before and after it removes words.
It prints a warning when they are different.

Before you commit a fixture, read its diff. Make sure that it has no private data.

## Regression test for a bug on a real library

1. Capture the item: `--title` or `--rating-key`, and a new `--scenario`.
2. Write a test with the expected `fake.puts`. It fails.
3. Commit it as `test: ...`. Then fix, and commit `fix: ...`. See `docs/workflow.md`.
