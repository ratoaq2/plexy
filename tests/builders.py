"""Build Plex XML for tests: a video with parts and streams, with only the attributes that plexy reads.

See docs/testing.md.
"""

import typing
import xml.etree.ElementTree as ET

import babelfish
import plexapi.media

from plexy import Preferences, WatchingPreference

STREAM_TYPES = {"video": "1", "audio": "2", "subtitle": "3"}


def video(
    *parts: ET.Element,
    rating_key: int = 1,
    kind: str = "movie",
    section: int = 1,
    guids: typing.Iterable[str] = (),
    show_key: int = 100,
) -> ET.Element:
    """Return a Video element. `kind` is `movie` or `episode`. An episode belongs to the show `show_key`.

    `guids` are external IDs, for example `tmdb://11`. Use made-up IDs: a real ID shows a title.
    """
    elem = ET.Element(
        "Video",
        ratingKey=str(rating_key),
        key=f"/library/metadata/{rating_key}",
        guid=f"plex://{kind}/{rating_key}",
        type=kind,
        title=f"{kind.capitalize()} {rating_key}",
        librarySectionID=str(section),
    )
    if kind == "episode":
        elem.attrib.update(grandparentTitle="Show 1", parentIndex="1", index=str(rating_key))
        elem.attrib.update(
            grandparentRatingKey=str(show_key),
            grandparentKey=f"/library/metadata/{show_key}",
            grandparentGuid=f"plex://show/{show_key}",
        )
    else:
        elem.set("year", "2000")
    elem.extend(ET.Element("Guid", id=guid) for guid in guids)
    media = ET.SubElement(elem, "Media", id=str(rating_key))
    media.extend(parts or [part()])
    return elem


def show(rating_key: int = 100, section: int = 1, guids: typing.Iterable[str] = ()) -> ET.Element:
    """Return the Directory element of a show. Put it on the fake server with its episodes."""
    elem = ET.Element(
        "Directory",
        ratingKey=str(rating_key),
        key=f"/library/metadata/{rating_key}/children",
        guid=f"plex://show/{rating_key}",
        type="show",
        title="Show 1",
        librarySectionID=str(section),
    )
    elem.extend(ET.Element("Guid", id=guid) for guid in guids)
    return elem


def part(*streams: ET.Element, part_id: int = 1) -> ET.Element:
    """Return a Part element. The stream IDs are the stream index + 1."""
    elem = ET.Element("Part", id=str(part_id), key=f"/library/parts/{part_id}/0/file.mkv", file=f"/media/{part_id}.mkv")
    elem.extend(streams)
    return elem


def stream(
    kind: str,
    language: str | None,
    index: int,
    codec: str,
    selected: bool = False,
    default: bool = False,
    **attrs: str | None,
) -> ET.Element:
    """Return a Stream element. `language` is an IETF tag. `attrs` sets or removes (None) Plex attributes."""
    elem = ET.Element("Stream", id=str(index + 1), streamType=STREAM_TYPES[kind], index=str(index), codec=codec)
    if selected:
        elem.set("selected", "1")
    if default:
        elem.set("default", "1")
    if language:
        lang = babelfish.Language.fromietf(language)
        elem.attrib.update(language=lang.name, languageTag=language, languageCode=lang.alpha3)
        elem.attrib.update(displayTitle=lang.name, extendedDisplayTitle=f"{lang.name} ({codec.upper()})")
    for name, value in attrs.items():
        if value is None:
            elem.attrib.pop(name, None)
        else:
            elem.set(name, value)
    return elem


def video_stream(language: str | None, index: int = 0, **attrs: typing.Any) -> ET.Element:
    return stream("video", language, index, "h264", default=True, **attrs)


def audio(language: str | None, index: int, codec: str = "aac", **options: typing.Any) -> ET.Element:
    return stream("audio", language, index, codec, **options)


def subtitle(language: str | None, index: int, codec: str = "srt", **options: typing.Any) -> ET.Element:
    return stream("subtitle", language, index, codec, **options)


def media_part(elem: ET.Element) -> plexapi.media.MediaPart:
    """Return the first plexapi MediaPart of a Video element, with no server. Use it when no request is sent."""
    return plexapi.media.MediaPart(None, elem.find("Media/Part"), initpath=elem.get("key"))


def preferences(watching_preference: WatchingPreference, language: str, **options: typing.Any) -> Preferences:
    values: dict[str, typing.Any] = {
        "audio_codecs": set(),
        "excluded_audio_codecs": set(),
        "subtitle_codecs": set(),
        "excluded_subtitle_codecs": set(),
        "keep_selected_audio": False,
        "keep_selected_subtitle": False,
        "force_subtitles": False,
    }
    values.update(options)
    return Preferences(
        watching_preference=watching_preference, language=babelfish.Language.fromietf(language), **values
    )
