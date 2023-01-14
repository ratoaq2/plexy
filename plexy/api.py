import enum
import functools
import logging
import re
import typing

import babelfish

import plexapi.library
import plexapi.media
import plexapi.server
import plexapi.video

from trakit import trakit

from plexy.exceptions import InvalidTitle
from plexy.utils import get_expected_languages, get_title

logger = logging.getLogger(__name__)


@enum.unique
class AudioCodec(enum.Enum):
    DTS = 'dca'
    AAC = 'aac'
    DOLBY_DIGITAL = 'ac3'
    DOLBY_DIGITAL_PLUS = 'eac3'
    DOLBY_DIGITAL_TRUEHD = 'truehd'
    FLAC = 'flac'
    MP2 = 'mp2'
    MP3 = 'mp3'
    VORBIS = 'vorbis'
    PCM = 'pcm'


@enum.unique
class SubtitleCodec(enum.Enum):
    SRT = 'srt'
    PGS = 'pgs'
    VOBSUB = 'vobsub'
    ASS = 'ass'
    MOV = 'mov_text'
    CC = 'eia_608'
    DVB = 'dvb_subtitle'


@enum.unique
class WatchingPreference(enum.Enum):
    ORIGINAL = 'original'
    DUBBED = 'dubbed'


@enum.unique
class LibraryType(enum.Enum):
    MOVIE = 'movie'
    EPISODE = 'episode'


title_re = re.compile(r'^(?P<name>.*?)\s*((?:\((?P<year>\d{4})\))?\s*)(?:s(?P<season>\d+)(?:e(?P<episode>\d+))?)?$')


class Title:

    def __init__(self,
                 name: str,
                 year: typing.Optional[int],
                 season: typing.Optional[int],
                 episode: typing.Optional[int]):
        self.name = name
        self.year = year
        self.season = season
        self.episode = episode

    @staticmethod
    def from_string(string: str):
        match = title_re.match(string)
        if not match:
            raise InvalidTitle(f'{string} is an invalid title')

        values = match.groupdict()
        numbers: typing.Dict[str, int] = {}
        for name in ('year', 'season', 'episode'):
            value = values[name]
            if value is not None:
                numbers[name] = int(value)

        return Title(name=values['name'],
                     year=numbers.get('year'),
                     season=numbers.get('season'),
                     episode=numbers.get('episode'))

    @property
    def is_episode(self):
        return self.season is not None or self.episode is not None

    @property
    def is_only_name(self):
        return self.year is None and not self.is_episode

    def __str__(self):
        string = f'{self.name}'
        if self.year is not None:
            string += f' ({self.year:04d})'
        if self.season is not None:
            string += f' s{self.season:02d}'
        if self.episode is not None:
            string += f'e{self.episode:02d}'
        return string

    def __repr__(self):
        suffix = ''
        if self.year is not None:
            suffix += f' ({self.year:04d})'
        if self.season is not None:
            suffix += f' s{self.season:02d}'
        if self.episode is not None:
            suffix += f'e{self.episode:02d}'
        return f'<{self.__class__.__name__} [{self}]>'


class Settings:
    def __init__(self, url: str, token: str):
        self.url = url
        self.token = token

    def __repr__(self):
        return f'<{self.__class__.__name__} [{self.url}]>'


class Criteria:

    def __init__(self,
                 libraries: typing.List[str],
                 titles: typing.List[Title],
                 newer: typing.Optional[str],
                 older: typing.Optional[str]):
        self.libraries = libraries
        self.titles = titles
        self.newer = newer
        self.older = older

    def __matching_titles(self, lib_type: LibraryType):
        if lib_type == LibraryType.MOVIE:
            return [t for t in self.titles if not t.is_episode]

        return self.titles

    def __to_filter(self, names: typing.Union[str, typing.List[str]], lib_type: LibraryType):
        filters: typing.Dict[str, typing.Any] = {}
        if self.newer:
            filters['addedAt>>'] = self.newer
        if self.older:
            filters['addedAt<<'] = self.older
        if names:
            prefix = 'show' if lib_type == LibraryType.EPISODE else 'movie'
            filters[f'{prefix}.title'] = names

        return filters

    def to_filters(self, lib_type: LibraryType) -> typing.List[typing.Mapping[str, typing.Any]]:
        titles = self.__matching_titles(lib_type)
        if not titles:
            if not self.titles:
                return [self.__to_filter([], lib_type)]

            return []

        names = [t.name for t in titles if t.is_only_name]
        if len(names) == len(titles):
            return [self.__to_filter(names, lib_type)]

        filters: typing.List[typing.Mapping[str, typing.Any]] = []
        for title in titles:
            if title.is_episode and lib_type != LibraryType.EPISODE:
                continue

            cur_filter = self.__to_filter(title.name, lib_type)
            if title.year:
                cur_filter[f'{lib_type.value}.year'] = title.year
            if title.season:
                cur_filter['season.index'] = title.season
            if title.episode:
                cur_filter['episode.index'] = title.episode
            filters.append(cur_filter)

        return filters

    def __str__(self):
        text = ''
        if self.libraries:
            text += f' in {",".join(self.libraries)}'
        if self.titles:
            text += ' or'.join([f' with title "{t}"' for t in self.titles])
        if self.newer:
            text += f' newer than {self.newer}'
        if self.older:
            text += f' older than {self.older}'
        return text.strip()


class Preferences:

    def __init__(self,
                 watching_preference: WatchingPreference,
                 language: typing.Optional[babelfish.Language],
                 audio_codecs: typing.Set[str],
                 excluded_audio_codecs: typing.Set[str],
                 subtitle_codecs: typing.Set[str],
                 excluded_subtitle_codecs: typing.Set[str]):
        self.watching_preference = watching_preference
        self.language = language
        self.audio_codecs = audio_codecs
        self.excluded_audio_codecs = excluded_audio_codecs
        self.subtitle_codecs = subtitle_codecs
        self.excluded_subtitle_codecs = excluded_subtitle_codecs

    def __repr__(self):
        return f'<{self.__class__.__name__} [{self.watching_preference}]>'


class Video:

    def __init__(self, video: plexapi.video.Video):
        self.video = video

    @property
    def title(self):
        if self.type == 'episode':
            return f'{self.video.grandparentTitle} - {self.video.seasonEpisode} - {self.video.title}'
        return f'{self.video.title} ({self.video.year})'

    @property
    def type(self):
        return 'episode' if isinstance(self.video, plexapi.video.Episode) else 'movie'

    def save_preferences(self, preferences: Preferences):
        logger.debug('Retrieving information for %s', self.title)
        self.video.reload()
        medias: typing.List[plexapi.media.Media] = self.video.media
        logger.debug('Found %d medias for video %s', len(medias), self.title)
        changes: typing.List[Change] = []
        for media in medias:
            parts: typing.List[plexapi.media.MediaPart] = media.parts
            for part in parts:
                logger.debug('Inspecting %s', part.file)
                target = VideoPart(self.title, part)
                change = target.save_preferences(preferences)
                if change:
                    changes.append(change)

        return changes

    def __str__(self):
        return f'{self.title}'

    def __repr__(self):
        return f'<{self.__class__.__name__} - {self.title}]>'


class Stream:

    def __init__(self,
                 stream: plexapi.media.MediaPartStream,
                 language: babelfish.Language,
                 commentary: bool,
                 closed_caption: bool,
                 hearing_impaired: bool):
        self.stream = stream
        self.language = language
        self.commentary = commentary
        self.closed_caption = closed_caption or (self.subtitle_stream and self.subtitle_stream.codec == 'eia_608')
        self.hearing_impaired = hearing_impaired

    @staticmethod
    def from_stream(stream: plexapi.media.MediaPartStream):
        title = get_title(stream)
        expected_languages = get_expected_languages(stream)
        options = {'expected_language': expected_languages[0]} if len(expected_languages) == 1 else {}
        guessed = trakit(title, options) if title else {}

        if len(expected_languages) > 1:
            language = expected_languages[0]
        elif expected_languages:
            language = expected_languages[0] if 'language' not in guessed else guessed['language']
        else:
            language = guessed.get('language') or babelfish.Language('und')

        return Stream(stream,
                      language=language,
                      commentary=guessed.get('commentary', False),
                      hearing_impaired=guessed.get('hearing_impaired', False),
                      closed_caption=guessed.get('closed_caption', False))

    @property
    def index(self):
        return self.stream.index

    @property
    def selected(self):
        return self.stream.selected

    @property
    def default(self):
        return self.stream.default or False

    @property
    def codec(self):
        return self.stream.codec

    @property
    def format(self):
        return self.subtitle_stream.format if self.subtitle_stream else None

    @property
    def audio_stream(self):
        if isinstance(self.stream, plexapi.media.AudioStream):
            return typing.cast(plexapi.media.AudioStream, self.stream)

    @property
    def subtitle_stream(self):
        if isinstance(self.stream, plexapi.media.SubtitleStream):
            return typing.cast(plexapi.media.SubtitleStream, self.stream)

    def __str__(self):
        return f'{self.language}: {self.stream.displayTitle}'

    def __repr__(self):
        return f'<{self.__class__.__name__} - {self}]>'


class VideoPart:

    def __init__(self, title: str, media: plexapi.media.MediaPart):
        self.title = title
        self.media = media
        self.video_streams: typing.List[Stream] = [Stream.from_stream(stream) for stream in media.videoStreams()]
        self.audio_streams: typing.List[Stream] = [Stream.from_stream(stream) for stream in media.audioStreams()]
        self.subtitle_streams: typing.List[Stream] = [Stream.from_stream(stream) for stream in media.subtitleStreams()]

    @staticmethod
    def __get_lang_cmp(desired_language: babelfish.Language):

        def language_cmp(a: Stream, b: Stream):
            a_language = a.language
            b_language = b.language
            if a_language == b_language:
                for prop in ('commentary', 'closed_caption', 'hearing_impaired'):
                    a_prop = getattr(a, prop)
                    b_prop = getattr(b, prop)
                    if not a_prop and b_prop:
                        return -1
                    if a_prop and not b_prop:
                        return 1

                return 0
            elif a_language == desired_language:
                return -1
            elif b_language == desired_language:
                return 1
            elif a_language.alpha3 != b_language.alpha3:
                if a_language.alpha3 == desired_language.alpha3:
                    return -1
                elif b_language.alpha3 == desired_language.alpha3:
                    return 1
            else:
                if a_language.country == b_language.country:
                    if a_language.script == desired_language.script:
                        return -1
                    elif b_language.script == desired_language.script:
                        return 1
                else:
                    if a_language.country == desired_language.country:
                        return -1
                    elif b_language == desired_language.country:
                        return 1

            return (a.index > b.index) - (a.index < b.index)

        return language_cmp

    @property
    def part(self):
        return self.media

    @property
    def selected_audio(self):
        streams = [stream for stream in self.audio_streams if stream.selected]
        return streams[0] if streams else None

    @property
    def original_language(self):
        languages = [stream.language for stream in sorted(
            self.video_streams, key=lambda x: x.default, reverse=True) if stream.language]

        if languages:
            return languages[0]

        languages = [stream.language for stream in sorted(
            self.audio_streams, key=lambda x: x.default, reverse=True) if stream.language]

        if languages:
            return languages[0]

    @property
    def selected_subtitle(self):
        streams = [stream for stream in self.subtitle_streams if stream.selected]
        return streams[0] if streams else None

    def select_audio(self, selection: Stream):
        self.part.setDefaultAudioStream(selection.audio_stream)

    def unselect_subtitle(self):
        self.part.resetDefaultSubtitleStream()

    def select_subtitle(self, selection: Stream):
        self.part.setDefaultSubtitleStream(selection.subtitle_stream)

    def get_sorted_audio_streams(self, preferences: Preferences):
        target_language = preferences.language if (
                preferences.watching_preference == WatchingPreference.DUBBED) else self.original_language
        language_cmp = VideoPart.__get_lang_cmp(target_language)

        return sorted([audio for audio in self.audio_streams if (
                not preferences.audio_codecs or audio.codec in preferences.audio_codecs)
                         and audio.codec not in preferences.excluded_audio_codecs],
                      key=functools.cmp_to_key(language_cmp))

    def get_sorted_subtitle_streams(self, preferences: Preferences):
        language_cmp = VideoPart.__get_lang_cmp(preferences.language)

        return sorted([subtitle for subtitle in self.subtitle_streams if (
                not preferences.subtitle_codecs or subtitle.format in preferences.subtitle_codecs)
                      and subtitle.format not in preferences.excluded_subtitle_codecs],
                      key=functools.cmp_to_key(language_cmp))

    def save_preferences(self, preferences: Preferences):
        previous_selected_audio = self.selected_audio
        previous_selected_subtitle = self.selected_subtitle
        selected_subtitle = previous_selected_subtitle

        audio_streams = self.get_sorted_audio_streams(preferences)
        selected_audio = audio_streams[0] if audio_streams else previous_selected_audio
        if selected_audio != previous_selected_audio:
            logger.debug('%s - new audio track in %s selected: %s',
                         self.title,
                         selected_audio.language,
                         selected_audio)
            self.select_audio(selected_audio)

        selected_audio_lang = selected_audio.language if selected_audio else None
        if selected_audio_lang == preferences.language:
            if previous_selected_subtitle:
                logger.debug('%s - no subtitle selected', self.title)
                self.unselect_subtitle()
                selected_subtitle = None
        else:
            subtitle_streams = self.get_sorted_subtitle_streams(preferences)
            selected_subtitle = subtitle_streams[0] if len(subtitle_streams) else previous_selected_subtitle
            if selected_subtitle != previous_selected_subtitle:
                logger.debug('%s new subtitle in %s selected: %s',
                             self.title,
                             selected_subtitle.language,
                             selected_subtitle)
                self.select_subtitle(selected_subtitle)

        if selected_audio != previous_selected_audio or selected_subtitle != previous_selected_subtitle:
            return Change(self, previous_selected_audio, previous_selected_subtitle, selected_audio, selected_subtitle)

    def __str__(self):
        return f'{self.title}'

    def __repr__(self):
        return f'<{self.__class__.__name__} - {self.title}]>'


class Change:

    def __init__(self,
                 video: VideoPart,
                 previous_audio: Stream,
                 previous_subtitle: Stream,
                 audio: Stream,
                 subtitle: Stream):
        self.video = video
        self.previous_audio = previous_audio
        self.previous_subtitle = previous_subtitle
        self.audio = audio
        self.subtitle = subtitle

    def __repr__(self):
        return f'<{self.__class__.__name__} - {self.video}]>'


class Plex:

    def __init__(self, settings: Settings):
        self.plex = plexapi.server.PlexServer(baseurl=settings.url, token=settings.token)
        logger.debug('Connected to %s', settings.url)

    def __find_sections(self, criteria: Criteria):
        if not criteria.libraries:
            return self.plex.library.sections()

        sections: typing.List[plexapi.library.LibrarySection] = []
        for library in criteria.libraries:
            sections.append(self.plex.library.section(library))

        return sections

    def search(self, criteria: Criteria):
        sections = self.__find_sections(criteria)
        logger.debug('Found %d sections', len(sections))
        results: typing.List[Video] = []
        for section in sections:
            logger.debug('Entering section %s', section.title)
            if section.type == 'show':
                filters_list = criteria.to_filters(LibraryType.EPISODE)
                for filters in filters_list:
                    episodes: typing.List[plexapi.video.Episode] = section.all(libtype='episode', filters=filters)
                    logger.debug('Found %d episodes in section %s', len(episodes), section.title)
                    results.extend([Video(e) for e in episodes])

            if section.type == 'movie':
                filters_list = criteria.to_filters(LibraryType.MOVIE)
                for filters in filters_list:
                    movies: typing.List[plexapi.video.Movie] = section.all(libtype='movie', filters=filters)
                    logger.debug('Found %d movies in section %s', len(movies), section.title)
                    results.extend([Video(m) for m in movies])

        return results
