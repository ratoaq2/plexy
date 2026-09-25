import pytest

from plexy import InvalidTitle, Title


@pytest.mark.parametrize(
    ("string", "expected", "text"),
    [
        ("Movie 1", ("Movie 1", None, None, None), "Movie 1"),
        ("Movie 1 (2017)", ("Movie 1", 2017, None, None), "Movie 1 (2017)"),
        ("Movie: 2 (2017)", ("Movie: 2", 2017, None, None), "Movie: 2 (2017)"),
        ("Show 1 s01", ("Show 1", None, 1, None), "Show 1 s01"),
        ("Show 1 s01e02", ("Show 1", None, 1, 2), "Show 1 s01e02"),
        ("Show 1 s1e2", ("Show 1", None, 1, 2), "Show 1 s01e02"),
        ("Show 1 (2024) s01e02", ("Show 1", 2024, 1, 2), "Show 1 (2024) s01e02"),
    ],
)
def test_from_string(string: str, expected: tuple[str, int | None, int | None, int | None], text: str) -> None:
    # when
    title = Title.from_string(string)

    # then
    assert (title.name, title.year, title.season, title.episode) == expected
    assert str(title) == text


@pytest.mark.parametrize(
    ("string", "is_episode", "is_only_name"),
    [
        ("Movie 1", False, True),
        ("Movie 1 (2017)", False, False),
        ("Show 1 s01", True, False),
        ("Show 1 s01e02", True, False),
    ],
)
def test_kind(string: str, is_episode: bool, is_only_name: bool) -> None:
    # when
    title = Title.from_string(string)

    # then
    assert title.is_episode == is_episode
    assert title.is_only_name == is_only_name


def test_invalid_title() -> None:
    # when
    with pytest.raises(InvalidTitle, match="is an invalid title"):
        Title.from_string("Movie\n1")
