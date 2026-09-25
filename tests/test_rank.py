import typing
import xml.etree.ElementTree as ET

import pytest

from plexy import WatchingPreference
from plexy.api import AudioCodec, Stream, SubtitleCodec, VideoPart
from tests.builders import audio, media_part, part, preferences, subtitle, video, video_stream

DUBBED = WatchingPreference.DUBBED
ORIGINAL = WatchingPreference.ORIGINAL


def video_part(*streams: ET.Element) -> VideoPart:
    return VideoPart("Movie 1", media_part(video(part(*streams))))


@pytest.mark.parametrize(
    ("language", "streams", "expected"),
    [
        pytest.param("pt-BR", [subtitle("pt", 1), subtitle("pt-BR", 2)], 2, id="exact language"),
        pytest.param("pt-BR", [subtitle("en", 1), subtitle("pt", 2)], 2, id="same base language"),
        pytest.param("fr", [subtitle("de", 2), subtitle("en", 1)], 1, id="lower index"),
        pytest.param(
            "en",
            [subtitle("en", 1, title="SDH", extendedDisplayTitle="English SDH (SRT)"), subtitle("en", 2)],
            2,
            id="normal before SDH",
        ),
        pytest.param(
            "en",
            [subtitle("en", 1, title="CC", extendedDisplayTitle="English CC (SRT)"), subtitle("en", 2)],
            2,
            id="normal before closed caption",
        ),
        pytest.param(
            "en", [subtitle("en", 1, codec="eia_608"), subtitle("en", 2)], 2, id="normal before closed caption codec"
        ),
    ],
)
def test_subtitle_rank(language: str, streams: list[ET.Element], expected: int) -> None:
    # given
    target = video_part(audio("ja", 0, selected=True), *streams)

    # when
    chosen = target.choose_subtitle_track(preferences(DUBBED, language))

    # then
    assert chosen is not None
    assert chosen.index == expected


@pytest.mark.parametrize(
    ("watching_preference", "streams", "expected"),
    [
        pytest.param(DUBBED, [audio("ja", 1, selected=True), audio("en", 2)], 2, id="dubbed"),
        pytest.param(
            DUBBED,
            [audio("en", 1, title="Commentary", extendedDisplayTitle="English Commentary (AAC)"), audio("en", 2)],
            2,
            id="normal before commentary",
        ),
        pytest.param(
            ORIGINAL,
            [video_stream("ja"), audio("en", 1, selected=True), audio("ja", 2)],
            2,
            id="original language from the video stream",
        ),
        pytest.param(
            ORIGINAL,
            [video_stream(None), audio("en", 1, selected=True), audio("ja", 2, default=True)],
            2,
            id="original language from the default audio stream",
        ),
    ],
)
def test_audio_rank(watching_preference: WatchingPreference, streams: list[ET.Element], expected: int) -> None:
    # given
    target = video_part(*streams)

    # when
    chosen = target.choose_audio_track(preferences(watching_preference, "en"))

    # then
    assert chosen is not None
    assert chosen.index == expected


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        pytest.param({}, 2, id="no codec option"),
        pytest.param({"audio_codecs": {AudioCodec.AAC}}, 3, id="accepted codec"),
        pytest.param({"excluded_audio_codecs": {AudioCodec.DTS}}, 3, id="excluded codec"),
        pytest.param({"audio_codecs": {AudioCodec.FLAC}}, 1, id="no codec left keeps the selection"),
        pytest.param({"keep_selected_audio": True}, 1, id="keep selected"),
    ],
)
def test_audio_options(options: dict[str, typing.Any], expected: int) -> None:
    # given
    target = video_part(audio("ja", 1, selected=True), audio("en", 2, codec="dca"), audio("en", 3))

    # when
    chosen = target.choose_audio_track(preferences(DUBBED, "en", **options))

    # then
    assert chosen is not None
    assert chosen.index == expected


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        pytest.param({}, 2, id="no codec option"),
        pytest.param({"subtitle_codecs": {SubtitleCodec.SRT}}, 3, id="accepted codec"),
        pytest.param({"excluded_subtitle_codecs": {SubtitleCodec.PGS}}, 3, id="excluded codec"),
    ],
)
def test_subtitle_options(options: dict[str, typing.Any], expected: int) -> None:
    # given
    target = video_part(audio("ja", 0, selected=True), subtitle("en", 2, codec="pgs"), subtitle("en", 3))

    # when
    chosen = target.choose_subtitle_track(preferences(DUBBED, "en", **options))

    # then
    assert chosen is not None
    assert chosen.index == expected


@pytest.mark.xfail(
    strict=True,
    reason="get_title gives trakit only the longest title field. A flag word in a shorter field is lost.",
)
def test_flag_word_in_short_title() -> None:
    # given
    elem = video(part(subtitle("pt", 1, title="SDH", displayTitle="Portuguese", extendedDisplayTitle=None)))

    # when
    stream = Stream.from_stream(media_part(elem).subtitleStreams()[0])

    # then
    assert stream.hearing_impaired
