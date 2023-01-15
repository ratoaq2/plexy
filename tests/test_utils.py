import typing

from mockito import mock

import plexapi.media

import pytest

from plexy.utils import get_expected_languages, get_title


@pytest.mark.parametrize(
    'values, expected', [
        ({'title': 'a', 'displayTitle': 'a title', 'extendedDisplayTitle': 'an extended title'}, 'an extended title'),
        ({'title': 'a title', 'displayTitle': 'short', 'extendedDisplayTitle': None}, 'a title'),
        ({'title': 'abcde', 'displayTitle': 'title', 'extendedDisplayTitle': None}, 'title'),
        ({'title': None, 'displayTitle': None, 'extendedDisplayTitle': None}, None),
    ]
)
def test_get_title(values: typing.Mapping[str, typing.Optional[str]], expected: str):
    # given
    stream = mock(values, spec=plexapi.media.MediaPartStream)

    # when
    actual = get_title(stream)

    # then
    assert actual == expected


@pytest.mark.parametrize(
    'values, expected', [
        ({'languageCode': 'eng', 'language': 'English', 'languageTag': 'en'}, ['en']),
        ({'languageCode': 'por', 'language': 'Portuguese', 'languageTag': 'pt'}, ['pt']),
        ({'languageCode': 'por', 'language': 'Portuguese', 'languageTag': 'pt-BR'}, ['pt-BR']),
        ({'languageCode': None, 'language': 'Portuguese', 'languageTag': None}, ['pt']),
        ({'languageCode': None, 'language': None, 'languageTag': None}, []),
    ]
)
def test_get_expected_languages(values: typing.Mapping[str, typing.Optional[str]], expected: typing.List[str]):
    # given
    stream = mock(values, spec=plexapi.media.MediaPartStream)

    # when
    actual = get_expected_languages(stream)

    # then
    assert actual == expected
