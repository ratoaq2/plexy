"""Read-only tests on a real Plex server. They run only when PLEXY_TEST_CONFIG is set. See docs/testing.md."""

import importlib.util
import os
import typing
import urllib.parse
from pathlib import Path
from types import ModuleType

import plexapi.server
import pytest

from plexy import Criteria, Plex, Settings, Title
from plexy.cli import read_config
from tests.fakeplex import Request, has_route

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "capture_fixture.py"

pytestmark = pytest.mark.live


def load_capture() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capture_fixture", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


capture = load_capture()


class RecordingSession(capture.ReadOnlySession):  # type: ignore[name-defined]
    """A GET-only session that records each request."""

    def __init__(self) -> None:
        super().__init__()
        self.gets: list[Request] = []

    def request(self, method: str | bytes, url: str | bytes, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        parsed = urllib.parse.urlsplit(str(url))
        params = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
        params.update({k: str(v) for k, v in (kwargs.get("params") or {}).items()})
        self.gets.append(Request(parsed.path, params))
        return super().request(method, url, *args, **kwargs)


@pytest.fixture(scope="module")
def config() -> dict[str, typing.Any]:
    merged: dict[str, typing.Any] = {}
    for name in os.environ["PLEXY_TEST_CONFIG"].split(","):
        merged.update(read_config(name.strip()))
    return merged


@pytest.fixture(scope="module")
def items(config: dict[str, typing.Any]) -> dict[str, Title]:
    values = config.get("test_items") or {}
    missing = [kind for kind in ("movie", "show", "episode") if not values.get(kind)]
    if missing:
        pytest.fail(f"PLEXY_TEST_CONFIG must give test_items: {', '.join(missing)}. See docs/testing.md.")
    return {kind: Title.from_string(values[kind]) for kind in ("movie", "show", "episode")}


def search(
    config: dict[str, typing.Any], *titles: Title, session: typing.Any = None, **options: typing.Any
) -> list[typing.Any]:
    """Run Plex.search on the real server with a GET-only session. Return the plexapi videos."""
    plex = Plex(Settings(url=config["url"], token=config["token"]))
    plex._plex = plexapi.server.PlexServer(config["url"], config["token"], session=session or capture.ReadOnlySession())
    return [video.video for video in plex.search(Criteria(titles=list(titles), **options))]


def name_only(title: Title, season: int | None = None) -> Title:
    return Title(title.name, None, season, None)


def has_name(title: Title, plex_title: str) -> bool:
    """The Plex title filter matches a part of the title, with no case."""
    return title.name.casefold() in plex_title.casefold()


def test_fake_has_each_route(config: dict[str, typing.Any], items: dict[str, Title]) -> None:
    # given
    session = RecordingSession()

    # when
    videos = search(config, items["movie"], items["episode"], session=session)
    for video in videos:
        video.reload()

    # then
    assert videos
    assert [r for r in session.gets if not has_route(r)] == []


def test_movie(config: dict[str, typing.Any], items: dict[str, Title]) -> None:
    # given
    movie = items["movie"]

    # when
    by_name = search(config, name_only(movie))
    by_year = search(config, movie)

    # then
    assert any(has_name(movie, v.title) and v.year == movie.year for v in by_name)
    assert any(has_name(movie, v.title) for v in by_year)
    assert all(v.year == movie.year for v in by_year)


def test_show(config: dict[str, typing.Any], items: dict[str, Title]) -> None:
    # when
    videos = search(config, name_only(items["show"]))

    # then
    assert any(has_name(items["show"], v.grandparentTitle) for v in videos)


def test_season(config: dict[str, typing.Any], items: dict[str, Title]) -> None:
    # given
    episode = items["episode"]

    # when
    videos = search(config, name_only(episode, episode.season))

    # then
    assert any(has_name(episode, v.grandparentTitle) for v in videos)
    assert all(v.parentIndex == episode.season for v in videos)


def test_episode(config: dict[str, typing.Any], items: dict[str, Title]) -> None:
    # given
    episode = items["episode"]

    # when
    videos = search(config, episode)

    # then
    assert any(has_name(episode, v.grandparentTitle) for v in videos)
    assert all((v.parentIndex, v.index) == (episode.season, episode.episode) for v in videos)


def test_age(config: dict[str, typing.Any], items: dict[str, Title]) -> None:
    # given
    movie = items["movie"]

    # when
    older = search(config, movie, older_than="1h")
    newer = search(config, movie, newer_than="1h")

    # then
    assert any(has_name(movie, v.title) for v in older)
    assert not any(has_name(movie, v.title) for v in newer)


@pytest.mark.xfail(
    reason="to_filters sets episode.year for a show title with a year. It must set show.year. "
    "Not strict: the test passes when all the episodes of the show are from the show year.",
)
def test_show_year(config: dict[str, typing.Any], items: dict[str, Title]) -> None:
    # when
    by_name = search(config, name_only(items["show"]))
    by_year = search(config, items["show"])

    # then
    assert len(by_year) == len(by_name)
