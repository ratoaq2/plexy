import enum
import logging
import re
import typing

import babelfish

import click

from plexy import (
    AudioCodec,
    Change,
    Criteria,
    InvalidTitle,
    Plex,
    Preferences,
    Settings,
    SubtitleCodec,
    Title,
    WatchingPreference,
    __url__,
    __version__,
)

logger = logging.getLogger('plexy')


class EnumParamType(click.Choice):
    def __init__(self, enum_type: typing.Type[enum.Enum], case_sensitive=False):
        self.__enum_type = enum_type
        super().__init__(choices=[item.value for item in enum_type], case_sensitive=case_sensitive)

    def convert(self, value: typing.Any, param: typing.Optional[click.Parameter], ctx: typing.Optional[click.Context]):
        if value is None or isinstance(value, enum.Enum):
            return value

        converted_str = super().convert(value, param, ctx)
        return self.__enum_type(converted_str)


class LanguageParamType(click.ParamType):
    name = 'language'

    def convert(self, value: typing.Any, param: typing.Optional[click.Parameter], ctx: typing.Optional[click.Context]):
        try:
            return babelfish.Language.fromietf(value)
        except (babelfish.Error, ValueError):
            self.fail(f"{click.style(f'{value}', bold=True)} is not a valid language")


class AgeParamType(click.ParamType):
    name = 'age'
    language_re = re.compile(r'^(?:(?P<weeks>\d+?)w)?(?:(?P<days>\d+?)d)?(?:(?P<hours>\d+?)h)?$')

    def convert(self, value: typing.Any, param: typing.Optional[click.Parameter], ctx: typing.Optional[click.Context]):
        match = self.language_re.match(value)
        if not match:
            self.fail(f"{click.style(f'{value}', bold=True)} is not a valid age")

        return value


class TitleParamType(click.ParamType):
    name = 'title'

    def convert(self, value: typing.Any, param: typing.Optional[click.Parameter], ctx: typing.Optional[click.Context]):
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

T = typing.TypeVar('T')


class DebugProgressBar(typing.Generic[T]):

    def __init__(self, debug: bool, iterable: typing.Iterable[T], **kwargs):
        self.debug = debug
        self.iterable = iterable
        self.progressbar = click.progressbar(iterable, **kwargs)

    def __iter__(self) -> typing.Iterator[T]:
        if not self.debug:
            return self.progressbar.__iter__()

        yield from self.iterable

    def __enter__(self):
        if not self.debug:
            return self.progressbar.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self.debug:
            return self.progressbar.__exit__(exc_type, exc_val, exc_tb)


@click.group(context_settings={'max_content_width': 100}, epilog=f'Suggestions and bug reports: {__url__}')
@click.option('-u', '--url', required=True, help='Plex server address, e.g.: http://myserver:32400')
@click.option('-t', '--token', required=True, help='Plex token')
@click.version_option(__version__)
@click.pass_context
def plexy(ctx: click.Context, url: str, token: str):
    """Your Plex, your way."""
    ctx.obj = Settings(url=url, token=token)


@plexy.command()
@click.option('-L', '--library', multiple=True, help='Library to be used. e.g: Movies, Shows')
@click.option('-t', '--title', type=TITLE, multiple=True,
              help='Filter for titles in your library. It could refer to a movie, a show, a season or an episode. '
                   'e.g: Avatar, The Matrix (1999), The Boys s2, Chernobyl s01e03, Game of Thrones (2011) s03e09')
@click.option('-l', '--language', type=LANGUAGE, help='Desired watching language as IETF code, e.g.: en, pt-BR')
@click.option('-a', '--audio-codec', type=AUDIO_CODEC, multiple=True, help='Accepted audio codec')
@click.option('-A', '--excluded-audio-codec', type=AUDIO_CODEC, multiple=True, help='Excluded audio codec')
@click.option('-s', '--subtitle-codec', type=SUBTITLE_CODEC, multiple=True, help='Accepted subtitle codec')
@click.option('-S', '--excluded-subtitle-codec', type=SUBTITLE_CODEC, multiple=True, help='Excluded subtitle codec')
@click.option('-n', '--newer', type=AGE, help='Filter movies/episodes newer than AGE, e.g. 12h, 1w2d.')
@click.option('-o', '--older', type=AGE, help='Filter movies/episodes older than AGE, e.g. 12h, 1w2d.')
@click.option('-f', '--full-summary', is_flag=True, help='Print the full summary of changed preferences.')
@click.option('--debug', is_flag=True, help='Print useful information for debugging and for reporting bugs.')
@click.argument('watching-preference', required=True, type=WATCHING_PREFERENCE, nargs=1)
@click.pass_obj
def preferences(settings: Settings,
                library: typing.Tuple[str],
                title: typing.Tuple[Title],
                language: typing.Optional[babelfish.Language],
                audio_codec: typing.Tuple[str],
                excluded_audio_codec: typing.Tuple[str],
                subtitle_codec: typing.Tuple[str],
                excluded_subtitle_codec: typing.Tuple[str],
                newer: typing.Optional[str],
                older: typing.Optional[str],
                watching_preference: WatchingPreference,
                full_summary: bool,
                debug: bool):
    """Your watching preferences

    \b
    Dubbed prefers an audio track with the desired language.
    Original prefers the original audio and an additional subtitle track if the audio is not in the desired language.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    prefs = Preferences(watching_preference=watching_preference,
                        language=language,
                        audio_codecs=set(audio_codec),
                        excluded_audio_codecs=set(excluded_audio_codec),
                        subtitle_codecs=set(subtitle_codec),
                        excluded_subtitle_codecs=set(excluded_subtitle_codec))
    criteria = Criteria(libraries=list(library), titles=list(title), newer=newer, older=older)

    videos = Plex(settings).search(criteria)

    changes: typing.List[Change] = []
    total_count: typing.Dict[str, int] = {'movie': 0, 'episode': 0}
    changed_count: typing.Dict[str, int] = dict(total_count)

    if not videos:
        click.echo(f'No video found {criteria}')
        return

    progressbar = DebugProgressBar(debug,
                                   videos,
                                   label='Configuring watching preferences',
                                   item_show_func=lambda item: (item and item.title) or '')
    with progressbar as bar:
        for v in bar:
            total_count[v.type] += 1
            cur_changes = v.save_preferences(prefs)
            if cur_changes:
                changed_count[v.type] += 1
                if full_summary:
                    changes.extend(cur_changes)

    for t in ('movie', 'episode'):
        if total_count[t]:
            click.echo(f"{click.style(str(changed_count[t]), bold=True, fg='green')} "
                       f"{t}{'s' if changed_count[t] > 1 else ''} changed out of "
                       f"{click.style(str(total_count[t]), bold=True, fg='blue')} "
                       f"selected {t}{'s' if total_count[t] > 1 else ''}")

    for change in changes:
        texts: typing.List[str] = []
        if change.previous_audio != change.audio:
            texts.append(f'changed audio from {click.style(str(change.previous_audio), bold=True, fg="yellow")} '
                         f'to {click.style(str(change.audio), bold=True, fg="green")}')
        if change.previous_subtitle != change.subtitle:
            if not change.previous_subtitle:
                texts.append(f'changed from {click.style("no", bold=True, fg="yellow")} subtitles '
                             f'to {click.style(str(change.subtitle), bold=True, fg="green")} subtitles')
            elif not change.subtitle:
                texts.append(f'changed from {click.style(str(change.previous_subtitle), bold=True, fg="yellow")} '
                             f'to {click.style("no", bold=True, fg="green")} subtitles')
            else:
                texts.append(f'changed subtitles from '
                             f'{click.style(str(change.previous_subtitle), bold=True, fg="yellow")} '
                             f'to {click.style(str(change.subtitle), bold=True, fg="green")}')

        click.echo(f'{click.style(str(change.video), bold=True, fg="blue")} {" and ".join(texts)}')
