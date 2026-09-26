import logging
import typing
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import requests
from requests.adapters import HTTPAdapter

from plexy import Criteria, Plex, Settings, WatchingPreference
from plexy.original_language import TMDB_URL, OriginalLanguages, tmdb_session
from tests.builders import audio, part, preferences, show, video, video_stream
from tests.conftest import URL
from tests.fakeplex import FakePlex, Request
from tests.faketmdb import Answer, FakeTmdb

FakePlexFactory = typing.Callable[..., FakePlex]
KEY = "0123456789abcdef0123456789abcdef"
TOKEN = "eyJhbGciOiJIUzI1NiJ9.e30.token"


def movie(rating_key: int, *guids: str) -> ET.Element:
    """A movie with an English video stream and default audio, and a Japanese audio track (stream ID 3)."""
    streams = [video_stream("en"), audio("en", 1, selected=True, default=True), audio("ja", 2)]
    return video(part(*streams, part_id=rating_key), rating_key=rating_key, guids=guids)


def episode(rating_key: int) -> ET.Element:
    streams = [video_stream("en"), audio("en", 1, selected=True, default=True), audio("ja", 2)]
    return video(part(*streams, part_id=rating_key), rating_key=rating_key, kind="episode", section=2)


def japanese(part_id: int) -> Request:
    return Request(f"/library/parts/{part_id}", {"allParts": "1", "audioStreamID": "3"})


def run(tmdb: FakeTmdb, cache: Path | None = None, key: str = KEY, **options: typing.Any) -> None:
    languages = OriginalLanguages(key, str(cache) if cache else None, session=tmdb)
    prefs = preferences(options.pop("watching_preference", WatchingPreference.ORIGINAL), "en", **options)
    for item in Plex(Settings(url=URL, token="token")).search(Criteria()):
        item.save_preferences(prefs, languages)


def test_tmdb_language_wins_over_the_media(fake_plex: FakePlexFactory) -> None:
    # given
    fake = fake_plex(items=[movie(1, "imdb://tt1", "tmdb://11")])
    tmdb = FakeTmdb({"movie/11": "ja"})

    # when
    run(tmdb)

    # then
    assert tmdb.paths == ["movie/11"]
    assert fake.puts == [japanese(1)]


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param("de", id="no track in the TMDB language"),
        pytest.param("xx", id="TMDB code that is not a language"),
        pytest.param(None, id="no language in the TMDB answer"),
    ],
)
def test_media_logic_when_tmdb_gives_no_usable_language(fake_plex: FakePlexFactory, answer: Answer) -> None:
    # given
    fake = fake_plex(items=[movie(1, "tmdb://11")])

    # when
    run(FakeTmdb({"movie/11": answer}))

    # then
    assert fake.puts == []


def test_no_tmdb_guid_sends_no_request(fake_plex: FakePlexFactory) -> None:
    # given
    fake = fake_plex(items=[movie(1, "imdb://tt1")])
    tmdb = FakeTmdb()

    # when
    run(tmdb)

    # then
    assert tmdb.paths == []
    assert fake.puts == []


@pytest.mark.parametrize(
    "options",
    [
        pytest.param({"watching_preference": WatchingPreference.DUBBED}, id="dubbed"),
        pytest.param({"keep_selected_audio": True}, id="keep selected audio"),
    ],
)
def test_no_request_when_the_original_language_is_not_used(
    fake_plex: FakePlexFactory, options: dict[str, typing.Any]
) -> None:
    # given
    fake_plex(items=[movie(1, "tmdb://11")])
    tmdb = FakeTmdb({"movie/11": "ja"})

    # when
    run(tmdb, **options)

    # then
    assert tmdb.paths == []


@pytest.mark.parametrize("answer", ["ja", "xx"])
def test_cache_hit_sends_no_request(fake_plex: FakePlexFactory, tmp_path: Path, answer: Answer) -> None:
    # given
    fake_plex(items=[movie(1, "tmdb://11")])
    cache = tmp_path / "cache" / "original_languages.jsonl"
    run(FakeTmdb({"movie/11": answer}), cache)
    tmdb = FakeTmdb()

    # when
    run(tmdb, cache)

    # then
    assert tmdb.paths == []
    assert OriginalLanguages(KEY, str(cache)).cache == {"plex://movie/1": answer}


def test_invalid_cache_line_is_ignored(tmp_path: Path) -> None:
    # given
    cache = tmp_path / "original_languages.jsonl"
    cache.write_text('{"plex://movie/1": "ja"}\n{"plex://mov', encoding="utf-8")

    # when
    languages = OriginalLanguages(KEY, str(cache))

    # then
    assert languages.cache == {"plex://movie/1": "ja"}


def test_episodes_use_the_show_guids(fake_plex: FakePlexFactory) -> None:
    # given
    fake = fake_plex(items=[show(100, section=2, guids=["tmdb://22"]), episode(1), episode(2)])
    tmdb = FakeTmdb({"tv/22": "ja"})

    # when
    run(tmdb)

    # then
    assert tmdb.paths == ["tv/22"]
    assert [r.path for r in fake.gets].count("/library/metadata/100") == 1
    assert fake.puts == [japanese(1), japanese(2)]


def test_not_found_continues_with_the_next_title(fake_plex: FakePlexFactory, tmp_path: Path) -> None:
    # given
    fake = fake_plex(items=[movie(1, "tmdb://11"), movie(2, "tmdb://12")])
    tmdb = FakeTmdb({"movie/12": "ja"})
    cache = tmp_path / "original_languages.jsonl"

    # when
    run(tmdb, cache)

    # then
    assert tmdb.paths == ["movie/11", "movie/12"]
    assert fake.puts == [japanese(2)]
    assert OriginalLanguages(KEY, str(cache)).cache == {"plex://movie/2": "ja"}


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(401, id="rejected key"),
        pytest.param(429, id="too many requests after the retries"),
        pytest.param(requests.ConnectionError(f"{TMDB_URL}/movie/11?api_key={KEY}"), id="connection error"),
    ],
)
def test_error_stops_tmdb_for_the_run(
    fake_plex: FakePlexFactory, tmp_path: Path, caplog: pytest.LogCaptureFixture, error: Answer
) -> None:
    # given
    fake = fake_plex(items=[movie(1, "tmdb://11"), movie(2, "tmdb://12")])
    tmdb = FakeTmdb({"movie/11": error, "movie/12": "ja"})
    cache = tmp_path / "original_languages.jsonl"

    # when
    with caplog.at_level(logging.DEBUG):
        run(tmdb, cache)

    # then
    assert tmdb.paths == ["movie/11"]
    assert fake.puts == []
    assert not cache.exists()
    assert "TMDB request for movie 11 failed" in caplog.text
    assert KEY not in caplog.text


@pytest.mark.parametrize(
    ("key", "headers", "params"),
    [
        pytest.param(TOKEN, {"Authorization": f"Bearer {TOKEN}"}, {}, id="read access token"),
        pytest.param(KEY, {}, {"api_key": KEY}, id="API key"),
    ],
)
def test_authentication(fake_plex: FakePlexFactory, key: str, headers: dict[str, str], params: dict[str, str]) -> None:
    # given
    fake_plex(items=[movie(1, "tmdb://11")])
    tmdb = FakeTmdb({"movie/11": "ja"})

    # when
    run(tmdb, key=key)

    # then
    assert tmdb.requests[0].headers == headers
    assert tmdb.requests[0].params == params


def test_session_waits_and_retries_on_too_many_requests() -> None:
    # when
    adapter = tmdb_session().get_adapter(f"{TMDB_URL}/movie/11")

    # then
    assert isinstance(adapter, HTTPAdapter)
    retry = adapter.max_retries
    assert retry.status_forcelist == [429]
    assert retry.status == 5
    assert retry.respect_retry_after_header
    assert (retry.connect, retry.read, retry.other) == (0, 0, 0)
