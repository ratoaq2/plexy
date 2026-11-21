import enum
import json
import logging
import os
import re
import typing
from pathlib import Path
from types import TracebackType

import babelfish
import click
from appdirs import AppDirs
from click.core import ParameterSource

from plexy import (
    AudioCodec,
    Change,
    Criteria,
    Error,
    InvalidTitle,
    Plex,
    Preferences,
    Settings,
    SubtitleCodec,
    Title,
    WatchingPreference,
    __title__,
    __url__,
    __version__,
)

logger = logging.getLogger(__title__)


class EnumParamType(click.Choice):
    def __init__(self, enum_type: type[enum.Enum], case_sensitive: bool = False) -> None:
        self.__enum_type = enum_type
        super().__init__(choices=[item.value for item in enum_type], case_sensitive=case_sensitive)

    def convert(self, value: typing.Any, param: click.Parameter | None, ctx: click.Context | None) -> typing.Any:
        if value is None or isinstance(value, enum.Enum):
            return value

        converted_str = super().convert(value, param, ctx)
        return self.__enum_type(converted_str)


class LanguageParamType(click.ParamType):
    name = "language"

    def convert(self, value: typing.Any, param: click.Parameter | None, ctx: click.Context | None) -> typing.Any:
        try:
            return babelfish.Language.fromietf(value)
        except (babelfish.Error, ValueError):
            self.fail(f"{click.style(f'{value}', bold=True)} is not a valid language")


class AgeParamType(click.ParamType):
    name = "age"
    age_re = re.compile(r"^(?:(?P<weeks>\d+?)w)?(?:(?P<days>\d+?)d)?(?:(?P<hours>\d+?)h)?$")

    def convert(self, value: typing.Any, param: click.Parameter | None, ctx: click.Context | None) -> typing.Any:
        match = self.age_re.match(value)
        if not match:
            self.fail(f"{click.style(f'{value}', bold=True)} is not a valid age")

        return value


class TitleParamType(click.ParamType):
    name = "title"

    def convert(self, value: typing.Any, param: click.Parameter | None, ctx: click.Context | None) -> typing.Any:
        try:
            return Title.from_string(value)
        except InvalidTitle:
            self.fail(f"{click.style(f'{value}', bold=True)} is not a valid title")


LANGUAGE = LanguageParamType()
AGE = AgeParamType()
WATCHING_PREFERENCE = EnumParamType(WatchingPreference)
TITLE = TitleParamType()

AUDIO_CODEC = EnumParamType(AudioCodec)
SUBTITLE_CODEC = EnumParamType(SubtitleCodec)

dirs = AppDirs(__title__)

# config key: env var. `<env var>_FILE` gives the path of a file with the secret, for example a Docker secret.
SECRET_ENVVARS = {"token": "PLEXY_TOKEN", "tmdb_key": "PLEXY_TMDB_KEY"}

T = typing.TypeVar("T")


class DebugProgressBar(typing.Generic[T]):
    def __init__(self, debug: bool, iterable: typing.Iterable[T], **kwargs: typing.Any) -> None:
        self.debug = debug
        self.iterable = iterable
        self.progressbar = click.progressbar(iterable, **kwargs)

    def __iter__(self) -> typing.Any:
        if not self.debug:
            return self.progressbar.__iter__()

        yield from self.iterable

    def __enter__(self) -> typing.Any:
        if not self.debug:
            return self.progressbar.__enter__()

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> typing.Any:
        if not self.debug:
            return self.progressbar.__exit__(exc_type, exc_val, exc_tb)


def read_config(config: str) -> typing.Any:
    with open(config, encoding="utf-8") as f:
        if config.endswith(".json"):
            return json.load(f)
        elif config.endswith(".yml") or config.endswith(".yaml"):
            import yaml

            return yaml.safe_load(f)
        else:
            raise click.BadParameter(f"Invalid config file {config}")


def set_default_config(ctx: click.Context, param: click.Parameter | None, config: str | None) -> str | None:
    default_map: dict[str, typing.Any] = {}

    # load first files from user config dir and current working dir
    for name, d in {"config": dirs.user_config_dir, __title__: os.getcwd()}.items():
        for ext in (".json", ".yml", ".yaml"):
            config_path = os.path.join(d, f"{name}{ext}")
            if os.path.isfile(config_path):
                default_map.update(read_config(config_path))

    if config and os.path.exists(config):
        # and override values with user provided config
        default_map.update(read_config(config))

    # a secret file overrides the config files. Click puts the command line and the env var before default_map.
    for key, envvar in SECRET_ENVVARS.items():
        path = os.environ.get(f"{envvar}_FILE")
        if not path:
            continue
        if os.environ.get(envvar):
            raise click.UsageError(f"Set {envvar} or {envvar}_FILE, not both.")
        try:
            default_map[key] = Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            raise click.UsageError(f"Cannot read {envvar}_FILE {path}") from None

    ctx.default_map = default_map

    return config


def secret_source(ctx: click.Context, key: str) -> str:
    """Tell where the secret comes from, for the debug log. Never the value."""
    envvar = SECRET_ENVVARS[key]
    source = ctx.get_parameter_source(key)
    if source == ParameterSource.COMMANDLINE:
        return f"--{key.replace('_', '-')}"
    if source == ParameterSource.ENVIRONMENT:
        return envvar
    if os.environ.get(f"{envvar}_FILE"):
        return f"{envvar}_FILE"
    return "config file"


@click.group(context_settings={"max_content_width": 100}, epilog=f"Suggestions and bug reports: {__url__}")
@click.option("-u", "--url", required=True, help="Plex server address, e.g.: http://myserver:32400")
@click.option("-t", "--token", required=True, envvar=SECRET_ENVVARS["token"], help="Plex token.")
@click.option(
    "--tmdb-key",
    envvar=SECRET_ENVVARS["tmdb_key"],
    help="TMDB read access token or API key. The original preference then gets the original language from TMDB.",
)
@click.option(
    "--user",
    help="Plex user to set the preferences for: a username, an email, or a display name. "
    "The token must belong to this user or to the server admin.",
)
@click.option(
    "--config",
    type=click.Path(exists=True),
    callback=set_default_config,
    is_eager=True,
    expose_value=False,
    help="Path to the config file.",
)
@click.version_option(__version__)
@click.pass_context
def plexy(ctx: click.Context, url: str, token: str, tmdb_key: str | None, user: str | None) -> None:
    """Your language, your way."""
    settings = Settings(
        url=url,
        token=token,
        tmdb_key=tmdb_key,
        cache_dir=dirs.user_cache_dir,
        token_source=secret_source(ctx, "token"),
        tmdb_key_source=secret_source(ctx, "tmdb_key") if tmdb_key else None,
        user=user,
    )
    ctx.obj = settings


@plexy.command()
@click.option("-L", "--library", multiple=True, help="Library to be used. e.g: Movies, Shows.")
@click.option(
    "-t",
    "--title",
    type=TITLE,
    multiple=True,
    help="Filter for titles in your library. It could refer to a movie, a show, a season or an episode. "
    "e.g: Avatar, The Matrix (1999), The Boys s2, Chernobyl s01e03, Game of Thrones (2011) s03e09",
)
@click.option("-l", "--language", type=LANGUAGE, help="Desired watching language as IETF code, e.g.: en, pt-BR.")
@click.option("-a", "--audio-codec", type=AUDIO_CODEC, multiple=True, help="Accepted audio codec.")
@click.option("-A", "--excluded-audio-codec", type=AUDIO_CODEC, multiple=True, help="Excluded audio codec.")
@click.option("-s", "--subtitle-codec", type=SUBTITLE_CODEC, multiple=True, help="Accepted subtitle codec.")
@click.option("-S", "--excluded-subtitle-codec", type=SUBTITLE_CODEC, multiple=True, help="Excluded subtitle codec.")
@click.option("-n", "--newer-than", type=AGE, help="Filter movies/episodes newer than AGE, e.g. 12h, 1w2d")
@click.option("-o", "--older-than", type=AGE, help="Filter movies/episodes older than AGE, e.g. 12h, 1w2d")
@click.option("-f", "--full-summary", is_flag=True, help="Print the full summary of changed preferences.")
@click.option("--skip-watching", is_flag=True, help="Skip movies/episodes that watch is in progress.")
@click.option(
    "--keep-selected-audio",
    is_flag=True,
    help="Do not change the selected audio. Useful when using original watching preference.",
)
@click.option("--keep-selected-subtitle", is_flag=True, help="Do not change the selected subtitle.")
@click.option(
    "--force-subtitles",
    is_flag=True,
    help="Select subtitles, even when the audio already matches the desired language.",
)
@click.option("--debug", is_flag=True, help="Print useful information for debugging and for reporting bugs.")
@click.argument("watching-preference", required=True, type=WATCHING_PREFERENCE, nargs=1)
@click.pass_obj
def preferences(
    settings: Settings,
    library: tuple[str],
    title: tuple[Title],
    language: babelfish.Language | None,
    audio_codec: tuple[str],
    excluded_audio_codec: tuple[str],
    subtitle_codec: tuple[str],
    excluded_subtitle_codec: tuple[str],
    newer_than: str | None,
    older_than: str | None,
    watching_preference: WatchingPreference,
    full_summary: bool,
    skip_watching: bool,
    keep_selected_audio: bool,
    keep_selected_subtitle: bool,
    force_subtitles: bool,
    debug: bool,
) -> None:
    """Your watching preferences

    \b
    Dubbed prefers an audio track with the desired language.
    Original prefers the original audio and an additional subtitle track if the audio is not in the desired language.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    prefs = Preferences(
        watching_preference=watching_preference,
        language=language,
        audio_codecs=set(audio_codec),
        excluded_audio_codecs=set(excluded_audio_codec),
        subtitle_codecs=set(subtitle_codec),
        excluded_subtitle_codecs=set(excluded_subtitle_codec),
        keep_selected_audio=keep_selected_audio,
        keep_selected_subtitle=keep_selected_subtitle,
        force_subtitles=force_subtitles,
    )
    criteria = Criteria(
        libraries=list(library),
        titles=list(title),
        newer_than=newer_than,
        older_than=older_than,
        skip_watching=skip_watching,
    )

    plex = Plex(settings)
    try:
        videos = plex.search(criteria)
    except Error as e:
        raise click.ClickException(str(e)) from None

    changes: list[Change] = []
    total_count: dict[str, int] = {"movie": 0, "episode": 0}
    changed_count: dict[str, int] = dict(total_count)

    if not videos:
        click.echo(f"No video found {criteria}")
        return

    progressbar = DebugProgressBar(
        debug, videos, label="Configuring watching preferences", item_show_func=lambda item: (item and item.title) or ""
    )
    with progressbar as bar:
        for v in bar:
            total_count[v.type] += 1
            cur_changes = v.save_preferences(prefs, plex.original_languages)
            if cur_changes:
                changed_count[v.type] += 1
                if full_summary:
                    changes.extend(cur_changes)

    for t in ("movie", "episode"):
        if total_count[t]:
            click.echo(
                f"{click.style(str(changed_count[t]), bold=True, fg='green')} "
                f"{t}{'s' if changed_count[t] > 1 else ''} changed out of "
                f"{click.style(str(total_count[t]), bold=True, fg='blue')} "
                f"selected {t}{'s' if total_count[t] > 1 else ''}"
            )

    for change in changes:
        texts: list[str] = []
        if change.previous_audio != change.audio:
            texts.append(
                f"changed audio from {click.style(str(change.previous_audio), bold=True, fg='yellow')} "
                f"to {click.style(str(change.audio), bold=True, fg='green')}"
            )
        if change.previous_subtitle != change.subtitle:
            if not change.previous_subtitle:
                texts.append(
                    f"changed from {click.style('no', bold=True, fg='yellow')} subtitles "
                    f"to {click.style(str(change.subtitle), bold=True, fg='green')} subtitles"
                )
            elif not change.subtitle:
                texts.append(
                    f"changed from {click.style(str(change.previous_subtitle), bold=True, fg='yellow')} "
                    f"to {click.style('no', bold=True, fg='green')} subtitles"
                )
            else:
                texts.append(
                    f"changed subtitles from "
                    f"{click.style(str(change.previous_subtitle), bold=True, fg='yellow')} "
                    f"to {click.style(str(change.subtitle), bold=True, fg='green')}"
                )

        click.echo(f"{click.style(str(change.video), bold=True, fg='blue')} {' and '.join(texts)}")
