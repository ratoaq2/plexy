"""Capture Plex items from a real server as test fixtures, with no private data.

The tool sends GET requests only. It keeps an allowlist of XML elements and attributes, renames all media
titles, and renumbers all IDs. See docs/testing.md.

    uv run python scripts/capture_fixture.py --config plexy.yml --title "Some Show s01e03" --scenario episode_1
    uv run python scripts/capture_fixture.py --config plexy.yml --server
"""

from __future__ import annotations

import argparse
import functools
import json
import pathlib
import re
import sys
import typing
import xml.etree.ElementTree as ET

import babelfish
import requests
import trakit

FIXTURES = pathlib.Path(__file__).resolve().parent.parent / "tests" / "fixtures"
SECTION_PLACEHOLDER = "SECTION"

FLAG_WORDS = """
sdh cc forced commentary commentaries director directors hearing impaired closed caption captions descriptive
description audio dubbed dub original external default signs songs full subtitles subtitle subs text
dts hd ma x truehd atmos ac3 eac3 e aac flac opus mp2 mp3 vorbis pcm dolby digital plus stereo mono surround
pgs srt ass ssa vobsub mov dvb eia wvtt webvtt smi lossless lossy
""".split()

VIDEO_ATTRS = {
    "movie": {"ratingKey", "key", "type", "title", "year", "librarySectionID", "librarySectionKey",
              "librarySectionTitle", "viewOffset"},
    "episode": {"ratingKey", "key", "type", "title", "year", "librarySectionID", "librarySectionKey",
                "librarySectionTitle", "viewOffset", "index", "parentIndex", "parentRatingKey", "parentKey",
                "parentTitle", "grandparentRatingKey", "grandparentKey", "grandparentTitle"},
}  # fmt: skip
MEDIA_ATTRS = {"id", "container", "audioCodec", "videoCodec", "audioChannels", "videoResolution"}
PART_ATTRS = {"id", "key", "file", "container"}
STREAM_ATTRS = {
    "streamType", "id", "index", "codec", "default", "selected", "forced", "hearingImpaired", "language",
    "languageCode", "languageTag", "title", "displayTitle", "extendedDisplayTitle", "channels",
    "audioChannelLayout", "key", "format", "profile",
}  # fmt: skip
STREAM_TEXT_ATTRS = ("language", "title", "displayTitle", "extendedDisplayTitle")
SECTION_ATTRS = {"key", "type", "title", "agent", "scanner", "language", "uuid", "filters", "allowSync",
                 "refreshing", "hidden", "content", "directory"}  # fmt: skip
ROOT_ATTRS = {"version", "platform", "apiVersion"}
SECTION_NAMES = {"movie": "Movies", "show": "Shows"}

word_re = re.compile(r"[^\W_]+(?:'[^\W_]+)?")


class ReadOnlySession(requests.Session):
    def request(self, method: str | bytes, url: str | bytes, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        if str(method).upper() != "GET":
            raise RuntimeError(f"Blocked a {method!s} request. The capture tool sends GET requests only.")
        return super().request(typing.cast(str, method), url, *args, **kwargs)


@functools.cache
def known_words() -> frozenset[str]:
    words: set[str] = set(FLAG_WORDS)
    config = json.loads((pathlib.Path(trakit.__file__).parent / "data" / "config.json").read_bytes())
    for group in ("countries", "implicit-languages", "languages", "regions", "scripts"):
        for name in config[group]:
            words.update(w.lower() for w in word_re.findall(name))
    for code in babelfish.LANGUAGE_MATRIX:
        words.update(w.lower() for w in word_re.findall(code.name))
    for code in babelfish.COUNTRY_MATRIX:
        words.update(w.lower() for w in word_re.findall(code.name))
    return frozenset(words)


class Renamer:
    """Gives new names and IDs, the same for the same real value, in one capture run."""

    def __init__(self) -> None:
        self.ids: dict[str, dict[str, str]] = {}
        self.names: dict[str, dict[str, str]] = {}
        self.sections: dict[str, tuple[str, str]] = {}
        self.words: dict[str, str] = {}
        self.warnings: list[str] = []

    def id(self, kind: str, real: str) -> str:
        table = self.ids.setdefault(kind, {})
        return table.setdefault(real, str(len(table) + 1))

    def name(self, kind: str, real: str, prefix: str) -> str:
        table = self.names.setdefault(kind, {})
        return table.setdefault(real, f"{prefix} {len(table) + 1}")

    def section(self, real: str, section_type: str) -> tuple[str, str]:
        if real not in self.sections:
            prefix = SECTION_NAMES[section_type]
            number = sum(1 for _, title in self.sections.values() if title.startswith(prefix)) + 1
            self.sections[real] = (self.id("section", real), prefix if number == 1 else f"{prefix} {number}")
        return self.sections[real]

    def text(self, value: str) -> str:
        def replace(match: re.Match[str]) -> str:
            word = match.group(0)
            if word.lower() in known_words() or any(c.isdigit() for c in word):
                return word
            if word not in self.words:
                self.words[word] = f"word{len(self.words) + 1}"
                self.warnings.append(f"Replaced an unknown word with {self.words[word]}. Review the stream titles.")
            return self.words[word]

        return word_re.sub(replace, value)


def keep(elem: ET.Element, attrs: set[str]) -> None:
    for name in list(elem.attrib):
        if name not in attrs:
            del elem.attrib[name]


def sanitize_item(container: ET.Element, renamer: Renamer, section_types: dict[str, str]) -> ET.Element:
    """Sanitize the XML of /library/metadata/<ratingKey>. `section_types` maps a real section ID to its type."""
    video = next(iter(container))
    kind = video.get("type", "")
    if kind not in VIDEO_ATTRS:
        raise ValueError(f"Cannot capture an item of type {kind!r}")

    real_section = video.get("librarySectionID", "")
    section_type = section_types.get(real_section, "movie" if kind == "movie" else "show")
    section_id, section_title = renamer.section(real_section, section_type)

    keep(video, VIDEO_ATTRS[kind])
    rating_key = renamer.id("item", video.get("ratingKey", ""))
    video.set("ratingKey", rating_key)
    video.set("key", f"/library/metadata/{rating_key}")
    video.set("librarySectionID", section_id)
    video.set("librarySectionKey", f"/library/sections/{section_id}")
    video.set("librarySectionTitle", section_title)
    if kind == "movie":
        video.set("title", renamer.name("movie", video.get("ratingKey", ""), "Movie"))
    else:
        show_key = renamer.id("item", video.get("grandparentRatingKey", ""))
        season_key = renamer.id("item", video.get("parentRatingKey", ""))
        video.set("title", renamer.name("episode", rating_key, "Episode"))
        video.set("grandparentRatingKey", show_key)
        video.set("grandparentKey", f"/library/metadata/{show_key}")
        video.set("grandparentTitle", renamer.name("show", show_key, "Show"))
        video.set("parentRatingKey", season_key)
        video.set("parentKey", f"/library/metadata/{season_key}")
        video.set("parentTitle", f"Season {video.get('parentIndex', '')}")

    for child in list(video):
        if child.tag != "Media":
            video.remove(child)
    for media in video:
        keep(media, MEDIA_ATTRS)
        media.set("id", renamer.id("media", media.get("id", "")))
        for part in list(media):
            if part.tag != "Part":
                media.remove(part)
                continue
            keep(part, PART_ATTRS)
            part_id = renamer.id("part", part.get("id", ""))
            container_ext = part.get("container", "mkv")
            part.set("id", part_id)
            part.set("key", f"/library/parts/{part_id}/0/file.{container_ext}")
            part.set("file", f"/media/{rating_key}.{container_ext}")
            for stream in list(part):
                if stream.tag != "Stream":
                    part.remove(stream)
                    continue
                sanitize_stream(stream, renamer)

    keep(container, {"size", "identifier", "allowSync", "librarySectionID", "librarySectionTitle"})
    container.set("size", "1")
    container.set("librarySectionID", section_id)
    container.set("librarySectionTitle", section_title)
    return container


def sanitize_stream(stream: ET.Element, renamer: Renamer) -> None:
    keep(stream, STREAM_ATTRS)
    for child in list(stream):
        stream.remove(child)
    stream_id = renamer.id("stream", stream.get("id", ""))
    stream.set("id", stream_id)
    if "key" in stream.attrib:
        stream.set("key", f"/library/streams/{stream_id}")
    for name in STREAM_TEXT_ATTRS:
        value = stream.get(name)
        if value:
            stream.set(name, renamer.text(value))


def sanitize_sections(container: ET.Element, renamer: Renamer) -> ET.Element:
    """Keep only the sections that the renamer has seen. Rename and renumber them."""
    for directory in list(container):
        real = directory.get("key", "")
        if real not in renamer.sections:
            container.remove(directory)
            continue
        new_id, title = renamer.sections[real]
        keep(directory, SECTION_ATTRS)
        for child in list(directory):
            directory.remove(child)
        directory.set("key", new_id)
        directory.set("title", title)
        directory.set("uuid", f"00000000-0000-0000-0000-{int(new_id):012d}")
    sections = sorted(container, key=lambda d: int(d.get("key", "0")))
    for directory in list(container):
        container.remove(directory)
    container.extend(sections)
    container.attrib = {"size": str(len(container)), "allowSync": "0", "title1": "Plex Library"}
    return container


def sanitize_root(container: ET.Element) -> ET.Element:
    keep(container, ROOT_ATTRS)
    container.set("friendlyName", "plexy-test")
    container.set("machineIdentifier", "0" * 40)
    container.set("myPlex", "0")
    for child in list(container):
        container.remove(child)
    return container


def sanitize_library(container: ET.Element) -> ET.Element:
    keep(container, {"size", "allowSync", "content", "identifier", "title1", "title2"})
    container.set("title1", "Plex Library")
    return container


def sanitize_section_meta(container: ET.Element, real_section: str, section_type: str) -> ET.Element:
    """Sanitize the filter types or collections of a section. Section IDs become a placeholder."""
    keep(container, {"allowSync", "identifier", "offset", "size", "totalSize", "viewGroup"})
    container.set("librarySectionID", SECTION_PLACEHOLDER)
    container.set("librarySectionTitle", SECTION_NAMES[section_type])
    container.set("size", "0")
    container.set("totalSize", "0")
    old = f"/library/sections/{real_section}/"
    for elem in container.iter():
        for name, value in elem.attrib.items():
            if old in value:
                elem.set(name, value.replace(old, f"/library/sections/{SECTION_PLACEHOLDER}/"))
    return container


def write(path: pathlib.Path, elem: ET.Element) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(elem)
    path.write_bytes(ET.tostring(elem, encoding="utf-8", xml_declaration=True) + b"\n")
    print(f"Wrote {path.relative_to(FIXTURES.parent.parent)} ({path.stat().st_size} B)")


def connect(configs: list[str]) -> typing.Any:
    import plexapi.server

    from plexy.cli import read_config

    config: dict[str, typing.Any] = {}
    for name in configs:
        config.update(read_config(name))
    return plexapi.server.PlexServer(baseurl=config["url"], token=config["token"], session=ReadOnlySession())


def find_items(server: typing.Any, titles: list[str], libraries: list[str], rating_keys: list[int]) -> list[typing.Any]:
    from plexy import Criteria, Plex, Settings, Title

    items = [server.fetchItem(key) for key in rating_keys]
    if titles:
        plex = Plex(Settings(url=server._baseurl, token=""))
        plex._plex = server
        criteria = Criteria(libraries=libraries, titles=[Title.from_string(t) for t in titles])
        items.extend(video.video for video in plex.search(criteria))
    if not items:
        raise SystemExit("No item found.")
    if len(items) > 20:
        raise SystemExit(f"{len(items)} items found. Give a more exact title. The limit is 20.")
    return items


def capture_scenario(server: typing.Any, items: list[typing.Any], scenario: pathlib.Path) -> None:
    renamer = Renamer()
    sections = server.query("/library/sections")
    section_types = {d.get("key", ""): d.get("type", "") for d in sections}
    for item in items:
        sanitized = sanitize_item(server.query(item.key), renamer, section_types)
        write(scenario / "metadata" / f"{next(iter(sanitized)).get('ratingKey')}.xml", sanitized)
    write(scenario / "sections.xml", sanitize_sections(sections, renamer))
    for warning in dict.fromkeys(renamer.warnings):
        print(f"Warning: {warning}", file=sys.stderr)


def capture_server(server: typing.Any) -> None:
    write(FIXTURES / "server" / "root.xml", sanitize_root(server.query("/")))
    write(FIXTURES / "server" / "library.xml", sanitize_library(server.query("/library")))
    for section_type in SECTION_NAMES:
        section = next((s for s in server.library.sections() if s.type == section_type), None)
        if section is None:
            raise SystemExit(f"The server has no {section_type} section.")
        for route, name in (("all", "filters"), ("collections", "collections")):
            meta = server.query(
                f"/library/sections/{section.key}/{route}?includeMeta=1&includeAdvanced=1"
                "&X-Plex-Container-Start=0&X-Plex-Container-Size=0"
            )
            write(
                FIXTURES / "server" / f"{name}_{section_type}.xml",
                sanitize_section_meta(meta, str(section.key), section_type),
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", action="append", required=True, help="Config file with url and token.")
    parser.add_argument("--scenario", help="Scenario folder name in tests/fixtures.")
    parser.add_argument("--title", action="append", default=[], help="Title, as the plexy --title option.")
    parser.add_argument("--library", action="append", default=[], help="Library name for --title.")
    parser.add_argument("--rating-key", action="append", type=int, default=[], help="Plex ratingKey of an item.")
    parser.add_argument("--server", action="store_true", help="Capture tests/fixtures/server/ too.")
    parser.add_argument("--force", action="store_true", help="Replace an existing scenario.")
    args = parser.parse_args()

    if not args.server and not args.scenario:
        parser.error("Give --scenario, --server, or both.")

    server = connect(args.config)
    if args.server:
        capture_server(server)
    if args.scenario:
        scenario = FIXTURES / args.scenario
        if scenario.exists() and not args.force:
            parser.error(f"{scenario} exists. Use --force to replace it.")
        for old in scenario.glob("metadata/*.xml"):
            old.unlink()
        capture_scenario(server, find_items(server, args.title, args.library, args.rating_key), scenario)
    print("Review the fixture diff for private data before you commit.")


if __name__ == "__main__":
    main()
