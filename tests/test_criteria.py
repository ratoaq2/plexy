import typing

import pytest

from plexy import Criteria, Title
from plexy.api import LibraryType

MOVIE = LibraryType.MOVIE
EPISODE = LibraryType.EPISODE


def criteria(*titles: str, **options: typing.Any) -> Criteria:
    return Criteria(titles=[Title.from_string(t) for t in titles], **options)


@pytest.mark.parametrize(
    ("given", "lib_type", "expected"),
    [
        pytest.param(criteria(), MOVIE, [{}], id="no title"),
        pytest.param(
            criteria(newer_than="2w", older_than="1d"),
            EPISODE,
            [{"addedAt>>": "2w", "addedAt<<": "1d"}],
            id="age",
        ),
        pytest.param(
            criteria("Movie 1", "Movie 2"), MOVIE, [{"movie.title": ["Movie 1", "Movie 2"]}], id="movie names"
        ),
        pytest.param(criteria("Show 1", "Show 2"), EPISODE, [{"show.title": ["Show 1", "Show 2"]}], id="show names"),
        pytest.param(
            criteria("Movie 1 (2017)", newer_than="2w"),
            MOVIE,
            [{"addedAt>>": "2w", "movie.title": "Movie 1", "movie.year": 2017}],
            id="movie year",
        ),
        pytest.param(
            criteria("Show 1 s01e02"),
            EPISODE,
            [{"show.title": "Show 1", "season.index": 1, "episode.index": 2}],
            id="episode",
        ),
        pytest.param(criteria("Show 1 s01e02"), MOVIE, [], id="episode on a movie library"),
        pytest.param(
            criteria("Movie 1", "Show 1 s01"), MOVIE, [{"movie.title": ["Movie 1"]}], id="movie and episode titles"
        ),
        pytest.param(
            criteria("Show 1", "Show 2 s01"),
            EPISODE,
            [{"show.title": "Show 1"}, {"show.title": "Show 2", "season.index": 1}],
            id="one filter for each title",
        ),
    ],
)
def test_to_filters(given: Criteria, lib_type: LibraryType, expected: list[dict[str, typing.Any]]) -> None:
    # when
    filters = given.to_filters(lib_type)

    # then
    assert filters == expected


@pytest.mark.xfail(
    strict=True,
    reason="to_filters sets episode.year for a show title with a year. It must set show.year.",
)
def test_show_year() -> None:
    # when
    filters = criteria("Show 1 (2024)").to_filters(EPISODE)

    # then
    assert filters == [{"show.title": "Show 1", "show.year": 2024}]
