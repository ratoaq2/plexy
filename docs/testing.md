# Testing

Tests do not connect to a real Plex server, except the live tests. They run the real plexy and plexapi code
on Plex XML that a fake server gives.

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

## Fake TMDB

`tests/faketmdb.py` has `FakeTmdb`, a `requests.Session` for the TMDB API. Give one answer for each path:

```python
tmdb = FakeTmdb({"movie/11": "ja", "movie/12": 500})
languages = OriginalLanguages("key", None, session=tmdb)
```

- A language code (or `None`) gives a `200` answer. A number gives that status. An exception is raised.
- A path with no answer gives `404`.
- `tmdb.requests` records each request: the path, the headers, and the parameters.
- CLI tests replace `plexy.original_language.tmdb_session` with a function that returns the fake.
- Use made-up TMDB IDs (`video(..., guids=["tmdb://11"])`). A real ID shows a title.

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

`tests/builders.py` makes small Plex XML in the test: `video`, `show`, `part`, `audio`, `subtitle`, and
`video_stream`. Use it for a rule of the stream selection. Use a fixture for a case from a real library.

```python
elem = video(part(audio("ja", 1, selected=True), audio("en", 2), subtitle("en", 3)))
```

- `media_part(elem)` gives a plexapi `MediaPart` with no server. `tests/test_rank.py` uses it with
  `VideoPart.choose_audio_track` and `VideoPart.choose_subtitle_track`.
- `fake_plex(items=[elem])` puts the video on the fake server. It copies the video, so a PUT does not
  change `elem`. Use it when the test checks `fake.puts`.
- The stream ID is the stream index + 1.
- `video(..., guids=[...])` adds `Guid` tags. An episode belongs to the show `show_key` (default `100`). Put
  `show(100, guids=[...])` on the fake server when plexy reads the show.

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

## Live tests

`tests/test_live.py` reads from a real Plex server. The tests have the `live` marker. They run only when
`PLEXY_TEST_CONFIG` is set. `scripts/test.sh` and CI skip them.

```
PLEXY_TEST_CONFIG=plexy.yml,plexy-test.yml uv run pytest -q --tb=short -m live tests
```

- `PLEXY_TEST_CONFIG` is a comma-separated list of config files (see `docs/cli.md`). A later file overrides
  an earlier file. They must give `url`, `token`, and `test_items`.
- The tests send GET requests only. The session of the capture tool blocks all other requests.
- The contract test runs the plexy search on the real server. Each request must have a route in `FakePlex`.
  When it fails, plexy or plexapi sends a new request. Add the route to `tests/fakeplex.py`.
- The filter tests check that Plex gives the expected item for each filter that plexy sends. The fake does
  not apply filters, so only these tests check what a filter means.

`test_items` names items of your library. Keep it in a local config file, for example `plexy-test.yml`.
`.gitignore` ignores `plexy*.yml`. Media titles must never go into the repo.

```yaml
test_items:
  movie: Some Movie (2017)
  show: Some Show (2024)
  episode: Some Show s01e02
```

- `movie`: a movie, with its year.
- `show`: a show, with its year.
- `episode`: an episode of a show, with no year.

## Regression test for a bug on a real library

1. Capture the item: `--title` or `--rating-key`, and a new `--scenario`.
2. Write a test with the expected `fake.puts`. It fails.
3. Commit it as `test: ...`. Then fix, and commit `fix: ...`. See `docs/workflow.md`.
