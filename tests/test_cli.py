import json
import logging
import types
import typing
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

from plexy import cli, original_language
from plexy.cli import SECRET_ENVVARS
from tests.builders import audio, part, subtitle, video, video_stream
from tests.conftest import URL
from tests.fakeplex import FakePlex
from tests.faketmdb import FakeTmdb

FakePlexFactory = typing.Callable[..., FakePlex]
Invoke = typing.Callable[..., Result]
SERVER = ["--url", URL, "--token", "token"]


@pytest.fixture
def invoke(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Invoke:
    """Run the CLI in an empty folder, with an empty user config folder. `files` are config files to write."""
    monkeypatch.setattr(
        cli,
        "dirs",
        types.SimpleNamespace(user_config_dir=str(tmp_path / "config"), user_cache_dir=str(tmp_path / "cache")),
    )
    monkeypatch.chdir(tmp_path)
    for envvar in SECRET_ENVVARS.values():
        monkeypatch.delenv(envvar, raising=False)
        monkeypatch.delenv(f"{envvar}_FILE", raising=False)

    def run(*args: str, files: dict[str, typing.Any] | None = None, env: dict[str, str] | None = None) -> Result:
        for name, content in (files or {}).items():
            path = tmp_path / name
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(content), encoding="utf-8")
        return CliRunner().invoke(cli.plexy, list(args), env=env)

    return run


@pytest.mark.parametrize(
    ("items", "expected"),
    [
        pytest.param(1, "1 movie changed out of 1 selected movie", id="one"),
        pytest.param(2, "2 movies changed out of 2 selected movies", id="two"),
    ],
)
def test_summary(invoke: Invoke, fake_plex: FakePlexFactory, items: int, expected: str) -> None:
    # given
    streams = [audio("ja", 1, selected=True), audio("en", 2)]
    fake_plex(items=[video(part(*streams, part_id=n), rating_key=n) for n in range(1, items + 1)])

    # when
    result = invoke(*SERVER, "preferences", "-l", "en", "dubbed")

    # then
    assert result.exit_code == 0, result.output
    assert expected in result.output


@pytest.mark.parametrize(
    ("args", "streams", "expected"),
    [
        pytest.param(
            ["-l", "en", "dubbed"],
            [audio("ja", 1, selected=True), audio("en", 2)],
            "Movie 1 (2000) changed audio from ja: Japanese to en: English",
            id="audio",
        ),
        pytest.param(
            ["-l", "en", "original"],
            [audio("ja", 1, selected=True), subtitle("en", 2)],
            "Movie 1 (2000) changed from no subtitles to en: English subtitles",
            id="new subtitle",
        ),
        pytest.param(
            ["-l", "de", "original"],
            [audio("ja", 1, selected=True), subtitle("pt-BR", 2, selected=True), subtitle("de", 3)],
            "Movie 1 (2000) changed subtitles from pt-BR: Portuguese to de: German",
            id="other subtitle",
        ),
        pytest.param(
            ["-l", "ja", "original"],
            [audio("ja", 1, selected=True), subtitle("pt-BR", 2, selected=True)],
            "Movie 1 (2000) changed from pt-BR: Portuguese to no subtitles",
            id="no subtitle",
        ),
    ],
)
def test_full_summary(
    invoke: Invoke, fake_plex: FakePlexFactory, args: list[str], streams: list[typing.Any], expected: str
) -> None:
    # given
    fake_plex(items=[video(part(*streams))])

    # when
    result = invoke(*SERVER, "preferences", "--full-summary", *args)

    # then
    assert result.exit_code == 0, result.output
    assert expected in result.output


def test_no_video_found(invoke: Invoke, fake_plex: FakePlexFactory) -> None:
    # given
    fake_plex(items=[])

    # when
    result = invoke(*SERVER, "preferences", "-t", "Movie 9", "-l", "en", "original")

    # then
    assert result.exit_code == 0, result.output
    assert 'No video found with title "Movie 9"' in result.output


@pytest.mark.parametrize(
    ("args", "files"),
    [
        pytest.param(
            ["preferences", "original"],
            {"config/config.json": {"url": URL, "token": "token", "preferences": {"language": "en"}}},
            id="user config folder",
        ),
        pytest.param(
            ["preferences", "original"],
            {
                "config/config.json": {"url": URL, "token": "token", "preferences": {"language": "pt-BR"}},
                "plexy.json": {"preferences": {"language": "en"}},
            },
            id="current folder overrides",
        ),
        pytest.param(
            ["--config", "other.json", "preferences", "original"],
            {
                "plexy.json": {"url": URL, "token": "token", "preferences": {"language": "pt-BR"}},
                "other.json": {"preferences": {"language": "en"}},
            },
            id="config option overrides",
        ),
    ],
)
def test_config_file(invoke: Invoke, fake_plex: FakePlexFactory, args: list[str], files: dict[str, typing.Any]) -> None:
    # given
    fake_plex("movie_1")

    # when
    result = invoke(*args, files=files)

    # then
    assert result.exit_code == 0, result.output
    assert "1 movie changed out of 1 selected movie" in result.output


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        pytest.param(["-l", "xx-YY"], "xx-YY is not a valid language", id="language"),
        pytest.param(["-n", "2d1w"], "2d1w is not a valid age", id="age"),
        pytest.param(["-t", "Movie\n1"], "is not a valid title", id="title"),
    ],
)
def test_invalid_option(invoke: Invoke, args: list[str], expected: str) -> None:
    # when
    result = invoke(*SERVER, "preferences", *args, "original")

    # then
    assert result.exit_code == 2
    assert expected in result.output


@pytest.mark.parametrize(
    ("args", "files"),
    [
        pytest.param([*SERVER, "--tmdb-key", "key"], {}, id="option"),
        pytest.param([], {"plexy.json": {"url": URL, "token": "token", "tmdb_key": "key"}}, id="config file"),
    ],
)
def test_tmdb_key(
    invoke: Invoke,
    fake_plex: FakePlexFactory,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    args: list[str],
    files: dict[str, typing.Any],
) -> None:
    # given
    streams = [video_stream("en"), audio("en", 1, selected=True, default=True), audio("ja", 2)]
    fake_plex(items=[video(part(*streams), guids=["tmdb://11"])])
    tmdb = FakeTmdb({"movie/11": "ja"})
    monkeypatch.setattr(original_language, "tmdb_session", lambda: tmdb)

    # when
    result = invoke(*args, "preferences", "-l", "en", "--full-summary", "original", files=files)

    # then
    assert result.exit_code == 0, result.output
    assert "changed audio from en: English to ja: Japanese" in result.output
    assert tmdb.requests[0].params == {"api_key": "key"}
    assert (tmp_path / "cache" / "original_languages.jsonl").is_file()


def test_no_tmdb_key_uses_the_media(
    invoke: Invoke, fake_plex: FakePlexFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    # given
    streams = [video_stream("en"), audio("en", 1, selected=True, default=True), audio("ja", 2)]
    fake_plex(items=[video(part(*streams), guids=["tmdb://11"])])
    tmdb = FakeTmdb({"movie/11": "ja"})
    monkeypatch.setattr(original_language, "tmdb_session", lambda: tmdb)

    # when
    result = invoke(*SERVER, "preferences", "-l", "en", "original")

    # then
    assert result.exit_code == 0, result.output
    assert "0 movie changed out of 1 selected movie" in result.output
    assert tmdb.requests == []


def test_debug(invoke: Invoke, fake_plex: FakePlexFactory) -> None:
    # given
    fake_plex("movie_1")

    # when
    result = invoke(*SERVER, "preferences", "--debug", "-l", "en", "original")

    # then
    assert result.exit_code == 0, result.output
    assert "1 movie changed out of 1 selected movie" in result.output


@pytest.mark.parametrize("key", ["token", "tmdb_key"])
@pytest.mark.parametrize(
    ("sources", "expected"),
    [
        pytest.param(["option"], "option", id="option"),
        pytest.param(["env"], "env", id="env"),
        pytest.param(["file"], "file", id="file"),
        pytest.param(["config"], "config", id="config"),
        pytest.param(["option", "env"], "option", id="option over env"),
        pytest.param(["option", "file"], "option", id="option over file"),
        pytest.param(["env", "config"], "env", id="env over config"),
        pytest.param(["file", "config"], "file", id="file over config"),
    ],
)
def test_secret_source(
    invoke: Invoke,
    fake_plex: FakePlexFactory,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    key: str,
    sources: list[str],
    expected: str,
) -> None:
    # given
    streams = [video_stream("en"), audio("en", 1, selected=True, default=True), audio("ja", 2)]
    fake = fake_plex(items=[video(part(*streams), guids=["tmdb://11"])])
    tmdb = FakeTmdb({"movie/11": "ja"})
    monkeypatch.setattr(original_language, "tmdb_session", lambda: tmdb)
    option = f"--{key.replace('_', '-')}"
    envvar = SECRET_ENVVARS[key]
    (tmp_path / "secret").write_text("file-secret\n", encoding="utf-8")
    args = ["--url", URL] + ([] if key == "token" else ["--token", "token"])
    env: dict[str, str] = {}
    config: dict[str, str] = {}
    if "option" in sources:
        args += [option, "option-secret"]
    if "env" in sources:
        env[envvar] = "env-secret"
    if "file" in sources:
        env[f"{envvar}_FILE"] = str(tmp_path / "secret")
    if "config" in sources:
        config[key] = "config-secret"

    # when
    with caplog.at_level(logging.DEBUG):
        result = invoke(*args, "preferences", "--debug", "-l", "en", "original", files={"plexy.json": config}, env=env)

    # then
    assert result.exit_code == 0, result.output
    sent = fake.tokens[0] if key == "token" else tmdb.requests[0].params["api_key"]
    assert sent == f"{expected}-secret"
    source = {"option": option, "env": envvar, "file": f"{envvar}_FILE", "config": "config file"}[expected]
    label = {"token": "Plex token", "tmdb_key": "TMDB key"}[key]
    assert f"{label} from {source}" in caplog.text
    assert sent not in result.output + caplog.text


@pytest.mark.parametrize("envvar", SECRET_ENVVARS.values())
def test_secret_env_and_file(invoke: Invoke, tmp_path: Path, envvar: str) -> None:
    # given
    (tmp_path / "secret").write_text("file-secret", encoding="utf-8")

    # when
    result = invoke(*SERVER, "preferences", "original", env={envvar: "env-secret", f"{envvar}_FILE": "secret"})

    # then
    assert result.exit_code == 2
    assert f"Set {envvar} or {envvar}_FILE, not both." in result.output
    assert "-secret" not in result.output


def test_secret_file_missing(invoke: Invoke) -> None:
    # when
    result = invoke(*SERVER, "preferences", "original", env={"PLEXY_TOKEN_FILE": "missing"})

    # then
    assert result.exit_code == 2
    assert "Cannot read PLEXY_TOKEN_FILE missing" in result.output


def plex_home(fake: FakePlex) -> None:
    """The admin account owns the server. Friend is a shared user. Kid is a managed user, with no username."""
    fake.account("admin-token", "admin", "admin@example.com", admin=True)
    fake.account("friend-token", "friend", "friend@example.com", title="Best Friend")
    fake.account("neighbor-token", "neighbor", "neighbor@example.com")
    fake.user(2, "friend-token", "Best Friend", username="friend", email="friend@example.com")
    fake.user(3, "kid-token", "Kid")


@pytest.mark.parametrize("user", ["friend", "FRIEND", "friend@example.com", "Best Friend"])
def test_user_owns_the_token(invoke: Invoke, fake_plex: FakePlexFactory, user: str) -> None:
    # given
    fake = fake_plex("movie_1")
    plex_home(fake)

    # when
    result = invoke("--url", URL, "--token", "friend-token", "--user", user, "preferences", "-l", "en", "original")

    # then
    assert result.exit_code == 0, result.output
    assert "1 movie changed out of 1 selected movie" in result.output
    assert fake.tokens == ["friend-token"]


@pytest.mark.parametrize(
    ("user", "expected"),
    [
        pytest.param("friend", "friend-token", id="username"),
        pytest.param("FRIEND@example.com", "friend-token", id="email"),
        pytest.param("kid", "kid-token", id="managed user"),
    ],
)
def test_user_switch_with_admin_token(invoke: Invoke, fake_plex: FakePlexFactory, user: str, expected: str) -> None:
    # given
    fake = fake_plex("movie_1")
    plex_home(fake)

    # when
    result = invoke("--url", URL, "--token", "admin-token", "--user", user, "preferences", "-l", "en", "original")

    # then
    assert result.exit_code == 0, result.output
    assert "1 movie changed out of 1 selected movie" in result.output
    assert fake.tokens == ["admin-token", expected]


@pytest.mark.parametrize(
    ("token", "user", "expected"),
    [
        pytest.param(
            "neighbor-token", "friend", "Error: The token belongs to neighbor, not to friend", id="other owner"
        ),
        pytest.param("admin-token", "nobody", "Error: Plex user nobody does not exist", id="unknown user"),
        pytest.param("admin-token", "ghost", "Error: Plex user ghost has no access to the server", id="no access"),
    ],
)
def test_user_error(invoke: Invoke, fake_plex: FakePlexFactory, token: str, user: str, expected: str) -> None:
    # given
    fake = fake_plex("movie_1")
    plex_home(fake)
    ET.SubElement(fake.users, "User", id="4", title="ghost")

    # when
    result = invoke("--url", URL, "--token", token, "--user", user, "preferences", "-l", "en", "original")

    # then
    assert result.exit_code == 1
    assert expected in result.output
    assert "Traceback" not in result.output
    assert "-token" not in result.output
    assert fake.searches == []


def test_no_user_sends_no_plex_tv_request(invoke: Invoke, fake_plex: FakePlexFactory) -> None:
    # given
    fake = fake_plex("movie_1")

    # when
    result = invoke(*SERVER, "preferences", "-l", "en", "original")

    # then
    assert result.exit_code == 0, result.output
    assert fake.plex_tv_requests == []
