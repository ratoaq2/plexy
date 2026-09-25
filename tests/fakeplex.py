"""A fake Plex server for tests: a requests.Session that serves XML fixtures and records the requests.

See docs/testing.md.
"""

import copy
import re
import typing
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SERVER = FIXTURES / "server"
SECTION_PLACEHOLDER = "SECTION"
SEARCH_TYPES = {"1": "movie", "4": "episode"}
SECTION_TYPES = {"movie": "movie", "episode": "show"}
STREAM_TYPES = {"audioStreamID": "2", "subtitleStreamID": "3"}

section_re = re.compile(r"^/library/sections/(?P<id>\d+)/(?P<route>all|collections)$")
metadata_re = re.compile(r"^/library/metadata/(?P<key>\d+)$")
part_re = re.compile(r"^/library/parts/(?P<id>\d+)$")


class Request(typing.NamedTuple):
    path: str
    params: dict[str, str]


class FakePlex(requests.Session):
    def __init__(self, sections: ET.Element, items: list[ET.Element]) -> None:
        super().__init__()
        self.sections = sections
        self.items: dict[str, ET.Element] = {}
        for container in items:
            video = container[0]
            self.items[video.get("ratingKey", "")] = container
        self.gets: list[Request] = []
        self.puts: list[Request] = []
        self.answers: list[tuple[dict[str, str], list[str]]] = []
        self.searched: set[tuple[str, str]] = set()

    @classmethod
    def from_folder(cls, scenario: str) -> "FakePlex":
        folder = FIXTURES / scenario
        items = [ET.parse(path).getroot() for path in sorted((folder / "metadata").glob("*.xml"))]
        return cls(ET.parse(folder / "sections.xml").getroot(), items)

    @classmethod
    def from_items(cls, videos: list[ET.Element]) -> "FakePlex":
        """Build a fake server from Video elements (see tests/builders.py). Sections come from the videos."""
        sections = ET.Element("MediaContainer")
        items: list[ET.Element] = []
        for video in videos:
            section_id = video.get("librarySectionID", "1")
            section_type = SECTION_TYPES[video.get("type", "movie")]
            if not any(d.get("key") == section_id for d in sections):
                title = {"movie": "Movies", "show": "Shows"}[section_type]
                ET.SubElement(sections, "Directory", key=section_id, type=section_type, title=title, filters="1")
            container = ET.Element("MediaContainer", size="1", librarySectionID=section_id)
            container.append(copy.deepcopy(video))
            items.append(container)
        sections.set("size", str(len(sections)))
        return cls(sections, items)

    def answer(self, query: dict[str, str], rating_keys: list[int]) -> None:
        """Give the result of each search that has all the `query` values. Other searches give no result."""
        self.answers.append((query, [str(key) for key in rating_keys]))

    def get(self, url: str | bytes, **kwargs: typing.Any) -> requests.Response:  # type: ignore[override]
        parsed = urllib.parse.urlsplit(str(url))
        params = dict(urllib.parse.parse_qsl(parsed.query))
        params.update({k: str(v) for k, v in (kwargs.get("params") or {}).items()})
        self.gets.append(Request(parsed.path, params))
        return self._response(str(url), self._route(parsed.path, params))

    def put(self, url: str | bytes, data: typing.Any = None, **kwargs: typing.Any) -> requests.Response:
        path = urllib.parse.urlsplit(str(url)).path
        params = {k: str(v) for k, v in (kwargs.get("params") or {}).items()}
        self.puts.append(Request(path, params))
        match = part_re.match(path)
        if not match:
            raise AssertionError(f"FakePlex has no route for PUT {path}")
        self._select(match.group("id"), params)
        return self._response(str(url), None)

    @property
    def searches(self) -> list[Request]:
        return [r for r in self.gets if section_re.match(r.path) and "type" in r.params]

    def _route(self, path: str, params: dict[str, str]) -> ET.Element:
        if path == "/":
            # A new PlexServer connects: a new plexy run starts.
            self.searched.clear()
            return ET.parse(SERVER / "root.xml").getroot()
        if path == "/library":
            return ET.parse(SERVER / "library.xml").getroot()
        if path == "/library/sections":
            return copy.deepcopy(self.sections)
        if match := metadata_re.match(path):
            if match.group("key") not in self.items:
                raise AssertionError(f"FakePlex has no item {match.group('key')}")
            return copy.deepcopy(self.items[match.group("key")])
        if match := section_re.match(path):
            section_id = match.group("id")
            if params.get("includeMeta") == "1":
                name = "filters" if match.group("route") == "all" else "collections"
                return self._section_meta(name, section_id)
            if match.group("route") == "all" and params.get("type") in SEARCH_TYPES:
                return self._search(section_id, params)
        raise AssertionError(f"FakePlex has no route for GET {path} {params}")

    def _section_meta(self, name: str, section_id: str) -> ET.Element:
        section_type = next(d.get("type", "") for d in self.sections if d.get("key") == section_id)
        text = (SERVER / f"{name}_{section_type}.xml").read_text(encoding="utf-8")
        text = text.replace(f"/library/sections/{SECTION_PLACEHOLDER}/", f"/library/sections/{section_id}/")
        text = text.replace(f'librarySectionID="{SECTION_PLACEHOLDER}"', f'librarySectionID="{section_id}"')
        return ET.fromstring(text.encode("utf-8"))

    def _search(self, section_id: str, params: dict[str, str]) -> ET.Element:
        kind = SEARCH_TYPES[params["type"]]
        keys = [
            key
            for key, container in self.items.items()
            if container[0].get("librarySectionID") == section_id and container[0].get("type") == kind
        ]
        if self.answers:
            answered = [ks for query, ks in self.answers if query.items() <= params.items()]
            keys = [key for key in keys if any(key in ks for ks in answered)]
        elif (section_id, kind) in self.searched:
            raise AssertionError(
                f"plexy searched section {section_id} for {kind} items two times. A real server gives a different "
                "result for each search. Give the results with FakePlex.answer()."
            )
        self.searched.add((section_id, kind))

        result = ET.Element("MediaContainer", size=str(len(keys)), totalSize=str(len(keys)), offset="0")
        result.set("librarySectionID", section_id)
        result.extend(copy.deepcopy(self.items[key][0]) for key in keys)
        return result

    def _select(self, part_id: str, params: dict[str, str]) -> None:
        part = next(
            (p for c in self.items.values() for p in c.iter("Part") if p.get("id") == part_id),
            None,
        )
        if part is None:
            raise AssertionError(f"FakePlex has no part {part_id}")
        for name, stream_type in STREAM_TYPES.items():
            if name not in params:
                continue
            for stream in part.iter("Stream"):
                if stream.get("streamType") == stream_type:
                    stream.attrib.pop("selected", None)
                    if stream.get("id") == params[name]:
                        stream.set("selected", "1")

    def _response(self, url: str, elem: ET.Element | None) -> requests.Response:
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response.encoding = "utf-8"
        response._content = b"" if elem is None else ET.tostring(elem, encoding="utf-8")
        return response
