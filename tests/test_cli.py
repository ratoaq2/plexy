import json
import types
import typing
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from plexy import cli, original_language
from tests.builders import audio, part, subtitle, video, video_stream
from tests.conftest import URL
from tests.fakeplex import FakePlex
from tests.faketmdb import FakeTmdb

FakePlexFactory = typing.Callable[..., FakePlex]
Invoke = typing.Callable[..., Result]
SERVER = ["--url", URL, "--token", "token"]


@pytest.fixture
def invoke(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Invoke:
    """Run the CLI in an empty folder, with an empty user config folder. `files` are config files to write."""
    monkeypatch.setattr(
        cli,
        "dirs",
        types.SimpleNamespace(user_config_dir=str(tmp_path / "config"), user_cache_dir=str(tmp_path / "cache")),
    )
    monkeypatch.chdir(tmp_path)

    def run(*args: str, files: dict[str, typing.Any] | None = None) -> Result:
        for name, content in (files or {}).items():
            path = tmp_path / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(content), encoding="utf-8")
        return CliRunner().invoke(cli.plexy, list(args))

    return run


@pytest.mark.parametrize(
    ("items", "expected"),
    [
        pytest.param(1, "1 movie changed out of 1 selected movie", id="one"),
        pytest.param(2, "2 movies changed out of 2 selected movies", id="two"),
    ],
)
def test_summary(invoke: Invoke, fake_plex: FakePlexFactory, items: int, expected: str) -> None:
    # given
    streams = [audio("ja", 1, selected=True), audio("en", 2)]
    fake_plex(items=[video(part(*streams, part_id=n), rating_key=n) for n in range(1, items + 1)])

    # when
    result = invoke(*SERVER, "preferences", "-l", "en", "dubbed")

    # then
    assert result.exit_code == 0, result.output
    assert expected in result.output


@pytest.mark.parametrize(
    ("args", "streams", "expected"),
    [
        pytest.param(
            ["-l", "en", "dubbed"],
            [audio("ja", 1, selected=True), audio("en", 2)],
            "Movie 1 (2000) changed audio from ja: Japanese to en: English",
            id="audio",
        ),
        pytest.param(
            ["-l", "en", "original"],
            [audio("ja", 1, selected=True), subtitle("en", 2)],
            "Movie 1 (2000) changed from no subtitles to en: English subtitles",
            id="new subtitle",
        ),
        pytest.param(
            ["-l", "de", "original"],
            [audio("ja", 1, selected=True), subtitle("pt-BR", 2, selected=True), subtitle("de", 3)],
            "Movie 1 (2000) changed subtitles from pt-BR: Portuguese to de: German",
            id="other subtitle",
        ),
        pytest.param(
            ["-l", "ja", "original"],
            [audio("ja", 1, selected=True), subtitle("pt-BR", 2, selected=True)],
            "Movie 1 (2000) changed from pt-BR: Portuguese to no subtitles",
            id="no subtitle",
        ),
    ],
)
def test_full_summary(
    invoke: Invoke, fake_plex: FakePlexFactory, args: list[str], streams: list[typing.Any], expected: str
) -> None:
    # given
    fake_plex(items=[video(part(*streams))])

    # when
    result = invoke(*SERVER, "preferences", "--full-summary", *args)

    # then
    assert result.exit_code == 0, result.output
    assert expected in result.output


def test_no_video_found(invoke: Invoke, fake_plex: FakePlexFactory) -> None:
    # given
    fake_plex(items=[])

    # when
    result = invoke(*SERVER, "preferences", "-t", "Movie 9", "-l", "en", "original")

    # then
    assert result.exit_code == 0, result.output
    assert 'No video found with title "Movie 9"' in result.output


@pytest.mark.parametrize(
    ("args", "files"),
    [
        pytest.param(
            ["preferences", "original"],
            {"config/config.json": {"url": URL, "token": "token", "preferences": {"language": "en"}}},
            id="user config folder",
        ),
        pytest.param(
            ["preferences", "original"],
            {
                "config/config.json": {"url": URL, "token": "token", "preferences": {"language": "pt-BR"}},
                "plexy.json": {"preferences": {"language": "en"}},
            },
            id="current folder overrides",
        ),
        pytest.param(
            ["--config", "other.json", "preferences", "original"],
            {
                "plexy.json": {"url": URL, "token": "token", "preferences": {"language": "pt-BR"}},
                "other.json": {"preferences": {"language": "en"}},
            },
            id="config option overrides",
        ),
    ],
)
def test_config_file(invoke: Invoke, fake_plex: FakePlexFactory, args: list[str], files: dict[str, typing.Any]) -> None:
    # given
    fake_plex("movie_1")

    # when
    result = invoke(*args, files=files)

    # then
    assert result.exit_code == 0, result.output
    assert "1 movie changed out of 1 selected movie" in result.output


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        pytest.param(["-l", "xx-YY"], "xx-YY is not a valid language", id="language"),
        pytest.param(["-n", "2d1w"], "2d1w is not a valid age", id="age"),
        pytest.param(["-t", "Movie\n1"], "is not a valid title", id="title"),
    ],
)
def test_invalid_option(invoke: Invoke, args: list[str], expected: str) -> None:
    # when
    result = invoke(*SERVER, "preferences", *args, "original")

    # then
    assert result.exit_code == 2
    assert expected in result.output


@pytest.mark.parametrize(
    ("args", "files"),
    [
        pytest.param([*SERVER, "--tmdb-key", "key"], {}, id="option"),
        pytest.param([], {"plexy.json": {"url": URL, "token": "token", "tmdb_key": "key"}}, id="config file"),
    ],
)
def test_tmdb_key(
    invoke: Invoke,
    fake_plex: FakePlexFactory,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    args: list[str],
    files: dict[str, typing.Any],
) -> None:
    # given
    streams = [video_stream("en"), audio("en", 1, selected=True, default=True), audio("ja", 2)]
    fake_plex(items=[video(part(*streams), guids=["tmdb://11"])])
    tmdb = FakeTmdb({"movie/11": "ja"})
    monkeypatch.setattr(original_language, "tmdb_session", lambda: tmdb)

    # when
    result = invoke(*args, "preferences", "-l", "en", "--full-summary", "original", files=files)

    # then
    assert result.exit_code == 0, result.output
    assert "changed audio from en: English to ja: Japanese" in result.output
    assert tmdb.requests[0].params == {"api_key": "key"}
    assert (tmp_path / "cache" / "original_languages.jsonl").is_file()


def test_no_tmdb_key_uses_the_media(
    invoke: Invoke, fake_plex: FakePlexFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # given
    streams = [video_stream("en"), audio("en", 1, selected=True, default=True), audio("ja", 2)]
    fake_plex(items=[video(part(*streams), guids=["tmdb://11"])])
    tmdb = FakeTmdb({"movie/11": "ja"})
    monkeypatch.setattr(original_language, "tmdb_session", lambda: tmdb)

    # when
    result = invoke(*SERVER, "preferences", "-l", "en", "original")

    # then
    assert result.exit_code == 0, result.output
    assert "0 movie changed out of 1 selected movie" in result.output
    assert tmdb.requests == []
