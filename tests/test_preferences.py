import typing

import pytest

from plexy import Criteria, Plex, Preferences, Settings, Title, WatchingPreference
from tests.builders import audio, part, preferences, video
from tests.builders import subtitle as subtitle_stream
from tests.conftest import URL
from tests.fakeplex import FakePlex, Request

FakePlexFactory = typing.Callable[..., FakePlex]


def run(criteria: Criteria, prefs: Preferences) -> int:
    videos = Plex(Settings(url=URL, token="token")).search(criteria)
    return sum(len(video.save_preferences(prefs)) for video in videos)


def subtitle(part_id: int, stream_id: int) -> Request:
    return Request(f"/library/parts/{part_id}", {"allParts": "1", "subtitleStreamID": str(stream_id)})


@pytest.mark.parametrize(
    ("language", "force_subtitles", "expected"),
    [
        ("en", False, [subtitle(1, 0)]),
        ("en", True, [subtitle(1, 4)]),
        ("pt-BR", False, []),
        ("de", False, [subtitle(1, 3)]),
    ],
)
def test_movie_original(
    fake_plex: FakePlexFactory, language: str, force_subtitles: bool, expected: list[Request]
) -> None:
    # given
    fake = fake_plex("movie_1")
    prefs = preferences(WatchingPreference.ORIGINAL, language, force_subtitles=force_subtitles)

    # when
    changes = run(Criteria(), prefs)

    # then
    assert fake.puts == expected
    assert changes == len(expected)


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        ("en", [subtitle(1, 0)]),
        ("pt-BR", []),
        ("pt", [subtitle(1, 33)]),
    ],
)
def test_episode_original(fake_plex: FakePlexFactory, language: str, expected: list[Request]) -> None:
    # given
    fake = fake_plex("episode_1")

    # when
    run(Criteria(), preferences(WatchingPreference.ORIGINAL, language))

    # then
    assert fake.puts == expected


def test_second_run_changes_nothing(fake_plex: FakePlexFactory) -> None:
    # given
    fake = fake_plex("movie_1")
    prefs = preferences(WatchingPreference.ORIGINAL, "en")
    run(Criteria(), prefs)
    fake.puts.clear()

    # when
    changes = run(Criteria(), prefs)

    # then
    assert fake.puts == []
    assert changes == 0


def test_search_sends_title_filter(fake_plex: FakePlexFactory) -> None:
    # given
    fake = fake_plex("movie_1")

    # when
    run(
        Criteria(libraries=["Movies"], titles=[Title.from_string("Movie 1")]),
        preferences(WatchingPreference.ORIGINAL, "pt-BR"),
    )

    # then
    assert [(r.path, r.params["type"], r.params.get("title")) for r in fake.searches] == [
        ("/library/sections/1/all", "1", "Movie 1")
    ]


def test_two_searches_need_answers(fake_plex: FakePlexFactory) -> None:
    # given
    fake_plex("movie_1")
    criteria = Criteria(titles=[Title.from_string("Movie 1 (2017)"), Title.from_string("Movie 2 (2018)")])

    # when
    with pytest.raises(AssertionError, match="two times"):
        run(criteria, preferences(WatchingPreference.ORIGINAL, "en"))


def test_two_searches_with_answers(fake_plex: FakePlexFactory) -> None:
    # given
    fake = fake_plex("movie_1")
    fake.answer({"title": "Movie 1", "year": "2017"}, [1])
    criteria = Criteria(titles=[Title.from_string("Movie 1 (2017)"), Title.from_string("Movie 2 (2018)")])

    # when
    changes = run(criteria, preferences(WatchingPreference.ORIGINAL, "en"))

    # then
    assert [r.params.get("title") for r in fake.searches] == ["Movie 1", "Movie 2"]
    assert fake.puts == [subtitle(1, 0)]
    assert changes == 1


def test_unknown_request_fails(fake_plex: FakePlexFactory) -> None:
    # given
    fake = fake_plex("movie_1")

    # when
    with pytest.raises(AssertionError, match="no route for GET /library/onDeck"):
        fake.get(f"{URL}/library/onDeck")


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        pytest.param({}, [subtitle(1, 0)], id="no subtitle"),
        pytest.param({"force_subtitles": True}, [subtitle(1, 4)], id="force subtitles"),
        pytest.param({"keep_selected_subtitle": True}, [], id="keep selected subtitle"),
    ],
)
def test_subtitle_options(fake_plex: FakePlexFactory, options: dict[str, typing.Any], expected: list[Request]) -> None:
    # given
    streams = [audio("en", 1, selected=True), subtitle_stream("pt", 2, selected=True), subtitle_stream("en", 3)]
    fake = fake_plex(items=[video(part(*streams))])

    # when
    run(Criteria(), preferences(WatchingPreference.DUBBED, "en", **options))

    # then
    assert fake.puts == expected
