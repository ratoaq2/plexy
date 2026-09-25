import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "capture_fixture.py"

PRIVATE = [
    "Secret Movie",
    "Secret Show",
    "Secret Episode",
    "Secret Season",
    "My Movies",
    "Grupo",
    "Fulano",
    "98765",
    "55555",
    "44444",
    "33333",
    "12345",
    "777",
    "/data/private",
    "plex://movie/abc",
    "a1b2c3d4-uuid",
    "A private summary",
    "totalSize",
    "my-server",
    "machine-0123",
    "someone@example.com",
]

MOVIE = """<MediaContainer size="1" totalSize="825" librarySectionID="777" librarySectionTitle="My Movies"
    librarySectionUUID="a1b2c3d4-uuid" identifier="com.plexapp.plugins.library">
  <Video ratingKey="98765" key="/library/metadata/98765" guid="plex://movie/abc" type="movie" title="Secret Movie"
      summary="A private summary" year="2017" librarySectionID="777" librarySectionKey="/library/sections/777"
      librarySectionTitle="My Movies" viewOffset="1000">
    <Media id="44444" container="mkv" audioCodec="dca">
      <Part id="55555" key="/library/parts/55555/1600000000/file.mkv" file="/data/private/Secret Movie.mkv"
          container="mkv" size="123456789">
        <Stream id="12345" streamType="1" index="0" codec="h264" languageCode="eng" default="1" displayTitle="1080p"/>
        <Stream id="12346" streamType="2" index="1" codec="dca" languageCode="eng" languageTag="en" selected="1"
            language="English" displayTitle="English (DTS 5.1)" extendedDisplayTitle="Grupo English (DTS 5.1)"
            title="Grupo"/>
        <Stream id="33333" key="/library/streams/33333" streamType="3" codec="srt" languageCode="por"
            languageTag="pt-BR" language="Portuguese" title="Fulano SDH" displayTitle="Portuguese"
            extendedDisplayTitle="Portuguese (Fulano SDH SRT External)"/>
      </Part>
    </Media>
    <Role tag="Someone Famous"/>
    <Chapter index="1"/>
  </Video>
</MediaContainer>"""

EPISODE = """<MediaContainer size="1" librarySectionID="888" librarySectionTitle="My Shows">
  <Video ratingKey="{key}" key="/library/metadata/{key}" type="episode" title="Secret Episode"
      grandparentTitle="{show}" grandparentRatingKey="{show_key}" grandparentKey="/library/metadata/{show_key}"
      parentTitle="Secret Season" parentRatingKey="{season_key}" parentIndex="1" index="{index}" year="2024"
      librarySectionID="888">
    <Media id="{key}"><Part id="{key}" container="mkv" file="/data/private/x.mkv"/></Media>
  </Video>
</MediaContainer>"""


@pytest.fixture(scope="module")
def cf() -> ModuleType:
    spec = importlib.util.spec_from_file_location("capture_fixture", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def text(elem: ET.Element) -> str:
    return ET.tostring(elem, encoding="unicode")


def episode(show: str, show_key: int, key: int, index: int) -> ET.Element:
    return ET.fromstring(EPISODE.format(show=show, show_key=show_key, season_key=show_key + 1, key=key, index=index))


def test_sanitize_item_removes_private_data(cf: ModuleType) -> None:
    # given
    renamer = cf.Renamer()

    # when
    actual = text(cf.sanitize_item(ET.fromstring(MOVIE), renamer, {"777": "movie"}))

    # then
    assert [value for value in PRIVATE if value in actual] == []


def test_sanitize_item_renames_and_renumbers(cf: ModuleType) -> None:
    # given
    renamer = cf.Renamer()

    # when
    video = next(iter(cf.sanitize_item(ET.fromstring(MOVIE), renamer, {"777": "movie"})))

    # then
    part = video.find("Media/Part")
    assert part is not None
    streams = part.findall("Stream")
    assert (video.get("ratingKey"), video.get("title"), video.get("year")) == ("1", "Movie 1", "2017")
    assert (video.get("librarySectionID"), video.get("librarySectionTitle")) == ("1", "Movies")
    assert video.get("viewOffset") == "1000"
    assert [child.tag for child in video] == ["Media"]
    assert part.attrib == {"id": "1", "key": "/library/parts/1/0/file.mkv", "file": "/media/1.mkv", "container": "mkv"}
    assert [s.get("id") for s in streams] == ["1", "2", "3"]
    assert streams[2].get("key") == "/library/streams/3"


def test_sanitize_item_keeps_stream_language_and_flags(cf: ModuleType) -> None:
    # given
    renamer = cf.Renamer()

    # when
    video = next(iter(cf.sanitize_item(ET.fromstring(MOVIE), renamer, {"777": "movie"})))

    # then
    subtitle = video.findall("Media/Part/Stream")[2]
    assert subtitle.get("languageTag") == "pt-BR"
    assert subtitle.get("title") == "word2 SDH"
    assert subtitle.get("extendedDisplayTitle") == "Portuguese (word2 SDH SRT External)"
    assert len(renamer.warnings) == 2


def test_sanitize_item_names_shows_the_same_in_one_run(cf: ModuleType) -> None:
    # given
    renamer = cf.Renamer()
    items = [episode("Secret Show", 100, 101, 1), episode("Secret Show", 100, 102, 2), episode("Other", 200, 201, 1)]

    # when
    videos = [next(iter(cf.sanitize_item(item, renamer, {"888": "show"}))) for item in items]

    # then
    assert [v.get("grandparentTitle") for v in videos] == ["Show 1", "Show 1", "Show 2"]
    assert [v.get("title") for v in videos] == ["Episode 1", "Episode 2", "Episode 3"]
    assert [v.get("parentTitle") for v in videos] == ["Season 1"] * 3
    assert videos[0].get("grandparentRatingKey") == videos[1].get("grandparentRatingKey")
    assert videos[0].get("librarySectionTitle") == "Shows"
    assert all("Secret" not in text(v) for v in videos)


def test_sanitize_sections_keeps_only_captured_sections(cf: ModuleType) -> None:
    # given
    renamer = cf.Renamer()
    cf.sanitize_item(ET.fromstring(MOVIE), renamer, {"777": "movie"})
    sections = ET.fromstring(
        """<MediaContainer size="2" title1="my-server">
          <Directory key="777" type="movie" title="My Movies" uuid="a1b2c3d4-uuid" agent="tv.plex.agents.movie">
            <Location id="1" path="/data/private"/>
          </Directory>
          <Directory key="778" type="movie" title="Secret Movie" uuid="other"/>
        </MediaContainer>"""
    )

    # when
    actual = cf.sanitize_sections(sections, renamer)

    # then
    assert [d.attrib for d in actual] == [
        {
            "key": "1",
            "type": "movie",
            "title": "Movies",
            "uuid": "00000000-0000-0000-0000-000000000001",
            "agent": "tv.plex.agents.movie",
        }
    ]
    assert [value for value in PRIVATE if value in text(actual)] == []


def test_sanitize_root_removes_server_identity(cf: ModuleType) -> None:
    # given
    root = ET.fromstring(
        """<MediaContainer friendlyName="my-server" machineIdentifier="machine-0123"
            myPlexUsername="someone@example.com" version="1.40.0" platform="Linux" certificate="1" size="25">
            <Directory key="x"/></MediaContainer>"""
    )

    # when
    actual = cf.sanitize_root(root)

    # then
    assert actual.attrib == {
        "version": "1.40.0",
        "platform": "Linux",
        "friendlyName": "plexy-test",
        "machineIdentifier": "0" * 40,
        "myPlex": "0",
    }
    assert list(actual) == []


def test_sanitize_section_meta_hides_section_id_and_size(cf: ModuleType) -> None:
    # given
    meta = ET.fromstring(
        """<MediaContainer size="0" totalSize="825" librarySectionID="777" librarySectionTitle="My Movies"
            librarySectionUUID="a1b2c3d4-uuid"><Meta><Type key="/library/sections/777/all?type=1" type="movie">
            <Filter filter="genre" key="/library/sections/777/genre"/></Type></Meta></MediaContainer>"""
    )

    # when
    actual = cf.sanitize_section_meta(meta, "777", "movie")

    # then
    assert actual.get("totalSize") == "0"
    assert actual.get("librarySectionTitle") == "Movies"
    assert "777" not in text(actual)
    assert "/library/sections/SECTION/genre" in text(actual)


def test_read_only_session_blocks_writes(cf: ModuleType) -> None:
    # given
    session = cf.ReadOnlySession()

    # when
    with pytest.raises(RuntimeError, match="GET requests only"):
        session.put("http://localhost:1/library/parts/1")
