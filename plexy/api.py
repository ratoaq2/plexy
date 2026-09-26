from __future__ import annotations

import enum
import functools
import logging
import os
import re
import typing

import babelfish
import plexapi.library
import plexapi.media
import plexapi.server
import plexapi.video
from trakit import trakit

from plexy.exceptions import InvalidTitle
from plexy.original_language import OriginalLanguages
from plexy.utils import get_expected_languages, get_title

logger = logging.getLogger(__name__)


@enum.unique
class AudioCodec(enum.Enum):
    DTS = "dca"
    AAC = "aac"
    OPUS = "opus"
    DOLBY_DIGITAL = "ac3"
    DOLBY_DIGITAL_PLUS = "eac3"
    DOLBY_DIGITAL_TRUEHD = "truehd"
    FLAC = "flac"
    MP2 = "mp2"
    MP3 = "mp3"
    VORBIS = "vorbis"
    PCM = "pcm"
    UNKNOWN = "unknown"


@enum.unique
class SubtitleCodec(enum.Enum):
    SRT = "srt"
    PGS = "pgs"
    VOBSUB = "vobsub"
    ASS = "ass"
    MOV = "mov_text"
    CC = "eia_608"
    DVB = "dvb_subtitle"
    UNKNOWN = "unknown"


@enum.unique
class WatchingPreference(enum.Enum):
    ORIGINAL = "original"
    DUBBED = "dubbed"


@enum.unique
class LibraryType(enum.Enum):
    MOVIE = "movie"
    EPISODE = "episode"


title_re = re.compile(r"^(?P<name>.*?)\s*((?:\((?P<year>\d{4})\))?\s*)(?:s(?P<season>\d+)(?:e(?P<episode>\d+))?)?$")


class Title:
    def __init__(self, name: str, year: int | None, season: int | None, episode: int | None):
        self.name = name
        self.year = year
        self.season = season
        self.episode = episode

    @staticmethod
    def from_string(string: str) -> Title:
        match = title_re.match(string)
        if not match:
            raise InvalidTitle(f"{string} is an invalid title")

        values = match.groupdict()
        numbers: dict[str, int] = {}
        for name in ("year", "season", "episode"):
            value = values[name]
            if value is not None:
                numbers[name] = int(value)

        return Title(
            name=values["name"], year=numbers.get("year"), season=numbers.get("season"), episode=numbers.get("episode")
        )

    @property
    def is_episode(self) -> bool:
        return self.season is not None or self.episode is not None

    @property
    def is_only_name(self) -> bool:
        return self.year is None and not self.is_episode

    def __str__(self) -> str:
        string = f"{self.name}"
        if self.year is not None:
            string += f" ({self.year:04d})"
        if self.season is not None:
            string += f" s{self.season:02d}"
        if self.episode is not None:
            string += f"e{self.episode:02d}"
        return string

    def __repr__(self) -> str:
        suffix = ""
        if self.year is not None:
            suffix += f" ({self.year:04d})"
        if self.season is not None:
            suffix += f" s{self.season:02d}"
        if self.episode is not None:
            suffix += f"e{self.episode:02d}"
        return f"<{self.__class__.__name__} [{self}]>"


class Settings:
    def __init__(self, url: str, token: str, tmdb_key: str | None = None, cache_dir: str | None = None):
        self.url = url
        self.token = token
        self.tmdb_key = tmdb_key
        self.cache_dir = cache_dir

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} [{self.url}]>"


class Criteria:
    def __init__(
        self,
        libraries: typing.Iterable[str] | None = None,
        titles: typing.Iterable[Title] | None = None,
        newer_than: str | None = None,
        older_than: str | None = None,
        skip_watching: bool = False,
    ):
        self.libraries = list(libraries or [])
        self.titles = list(titles or [])
        self.newer_than = newer_than
        self.older_than = older_than
        self.skip_watching = skip_watching

    def __matching_titles(self, lib_type: LibraryType) -> list[Title]:
        if lib_type == LibraryType.MOVIE:
            return [t for t in self.titles if not t.is_episode]

        return self.titles

    def __to_filter(self, names: str | list[str], lib_type: LibraryType) -> dict[str, typing.Any]:
        filters: dict[str, typing.Any] = {}
        if self.newer_than:
            filters["addedAt>>"] = self.newer_than
        if self.older_than:
            filters["addedAt<<"] = self.older_than
        if names:
            prefix = "show" if lib_type == LibraryType.EPISODE else "movie"
            filters[f"{prefix}.title"] = names

        return filters

    def to_filters(self, lib_type: LibraryType) -> list[typing.Mapping[str, typing.Any]]:
        titles = self.__matching_titles(lib_type)
        if not titles:
            if not self.titles:
                return [self.__to_filter([], lib_type)]

            return []

        names = [t.name for t in titles if t.is_only_name]
        if len(names) == len(titles):
            return [self.__to_filter(names, lib_type)]

        filters: list[typing.Mapping[str, typing.Any]] = []
        for title in titles:
            if title.is_episode and lib_type != LibraryType.EPISODE:
                continue

            cur_filter = self.__to_filter(title.name, lib_type)
            if title.year:
                cur_filter[f"{lib_type.value}.year"] = title.year
            if title.season:
                cur_filter["season.index"] = title.season
            if title.episode:
                cur_filter["episode.index"] = title.episode
            filters.append(cur_filter)

        return filters

    def __str__(self) -> str:
        text = ""
        if self.libraries:
            text += f" in {', '.join(self.libraries)}"
        if self.titles:
            text += " or".join([f' with title "{t}"' for t in self.titles])
        if self.newer_than:
            text += f" newer than {self.newer_than}"
        if self.older_than:
            text += f" older than {self.older_than}"
        if self.skip_watching:
            text += ' skipping "Continue Watching"'
        return text.strip()


class Preferences:
    def __init__(
        self,
        watching_preference: WatchingPreference,
        language: babelfish.Language | None,
        audio_codecs: set[str],
        excluded_audio_codecs: set[str],
        subtitle_codecs: set[str],
        excluded_subtitle_codecs: set[str],
        keep_selected_audio: bool,
        keep_selected_subtitle: bool,
        force_subtitles: bool,
    ):
        self.watching_preference = watching_preference
        self.language = language
        self.audio_codecs = audio_codecs
        self.excluded_audio_codecs = excluded_audio_codecs
        self.subtitle_codecs = subtitle_codecs
        self.excluded_subtitle_codecs = excluded_subtitle_codecs
        self.keep_selected_audio = keep_selected_audio
        self.keep_selected_subtitle = keep_selected_subtitle
        self.force_subtitles = force_subtitles

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} [{self.watching_preference}]>"


class Video:
    def __init__(self, video: plexapi.video.Video):
        self.video = video

    @staticmethod
    def accept(video: plexapi.video.Movie | plexapi.video.Episode, criteria: Criteria) -> bool:
        return not criteria.skip_watching or not video.viewOffset

    @property
    def title(self) -> str:
        if self.type == "episode":
            return f"{self.video.grandparentTitle} - {self.video.seasonEpisode} - {self.video.title}"
        return f"{self.video.title} ({self.video.year})"

    @property
    def type(self) -> str:
        return "episode" if isinstance(self.video, plexapi.video.Episode) else "movie"

    def save_preferences(
        self, preferences: Preferences, original_languages: OriginalLanguages | None = None
    ) -> list[Change]:
        logger.debug("Retrieving information for %s", self.title)
        self.video.reload()
        original_language = None
        if (
            original_languages
            and preferences.watching_preference == WatchingPreference.ORIGINAL
            and not preferences.keep_selected_audio
        ):
            original_language = original_languages.get(
                typing.cast("plexapi.video.Movie | plexapi.video.Episode", self.video)
            )
        medias: list[plexapi.media.Media] = self.video.media
        logger.debug("Found %d medias for video %s", len(medias), self.title)
        changes: list[Change] = []
        for media in medias:
            parts: list[plexapi.media.MediaPart] = media.parts
            for part in parts:
                logger.debug("Inspecting %s", part.file)
                target = VideoPart(self.title, part, original_language)
                change = target.save_preferences(preferences)
                if change:
                    changes.append(change)

        return changes

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Video):
            return typing.cast(bool, self.video == other.video)
        return NotImplemented

    def __hash__(self) -> int:
        return hash(tuple(sorted(self.__dict__.items())))

    def __str__(self) -> str:
        return f"{self.title}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} - {self.title}]>"


class Stream:
    def __init__(
        self,
        stream: plexapi.media.MediaPartStream,
        language: babelfish.Language,
        commentary: bool,
        closed_caption: bool,
        hearing_impaired: bool,
    ):
        self.stream = stream
        self.language = language
        self.commentary = commentary
        self.closed_caption = closed_caption or self.codec == SubtitleCodec.CC
        self.hearing_impaired = hearing_impaired

    @staticmethod
    def from_stream(stream: plexapi.media.MediaPartStream) -> Stream:
        title = get_title(stream)
        expected_languages = get_expected_languages(stream)
        options = {"expected_language": expected_languages[0]} if len(expected_languages) == 1 else {}
        guessed = trakit(title, options) if title else {}

        if len(expected_languages) > 1:
            language = expected_languages[0]
        elif expected_languages:
            language = expected_languages[0] if "language" not in guessed else guessed["language"]
        else:
            language = guessed.get("language") or babelfish.Language("und")

        return Stream(
            stream,
            language=language,
            commentary=guessed.get("commentary", False),
            hearing_impaired=guessed.get("hearing_impaired", False),
            closed_caption=guessed.get("closed_caption", False),
        )

    @property
    def index(self) -> int:
        return typing.cast(int, self.stream.index)

    @property
    def selected(self) -> bool:
        return typing.cast(bool, self.stream.selected)

    @property
    def default(self) -> bool:
        return self.stream.default or False

    @property
    def codec(self) -> AudioCodec | SubtitleCodec | None:
        audio_stream = self.audio_stream
        if audio_stream and audio_stream.codec:
            try:
                return AudioCodec(audio_stream.codec)
            except ValueError:
                return AudioCodec.UNKNOWN

        subtitle_stream = self.subtitle_stream
        if subtitle_stream and subtitle_stream.codec:
            try:
                return SubtitleCodec(subtitle_stream.codec)
            except ValueError:
                return SubtitleCodec.UNKNOWN

        return None

    @property
    def audio_stream(self) -> plexapi.media.AudioStream | None:
        if isinstance(self.stream, plexapi.media.AudioStream):
            return self.stream

        return None

    @property
    def subtitle_stream(self) -> plexapi.media.SubtitleStream | None:
        if isinstance(self.stream, plexapi.media.SubtitleStream):
            return self.stream

        return None

    def __str__(self) -> str:
        return f"{self.language}: {self.stream.displayTitle}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} - {self}]>"


class VideoPart:
    def __init__(self, title: str, media: plexapi.media.MediaPart, original_language: babelfish.Language | None = None):
        self.title = title
        self.media = media
        self.__original_language = original_language
        self.video_streams: list[Stream] = [Stream.from_stream(stream) for stream in media.videoStreams()]
        self.audio_streams: list[Stream] = [Stream.from_stream(stream) for stream in media.audioStreams()]
        self.subtitle_streams: list[Stream] = [Stream.from_stream(stream) for stream in media.subtitleStreams()]

    @staticmethod
    def __get_lang_cmp(desired_language: babelfish.Language) -> typing.Callable[[Stream, Stream], int]:

        def language_cmp(a: Stream, b: Stream) -> int:
            a_language = a.language
            b_language = b.language
            if a_language == b_language:
                for prop in ("commentary", "closed_caption", "hearing_impaired"):
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
                    elif b_language.country == desired_language.country:
                        return 1

            return (a.index > b.index) - (a.index < b.index)

        return language_cmp

    @property
    def part(self) -> plexapi.media.MediaPart:
        return self.media

    @property
    def selected_audio(self) -> Stream | None:
        streams = [stream for stream in self.audio_streams if stream.selected]
        return streams[0] if streams else None

    @property
    def original_language(self) -> babelfish.Language | None:
        language = self.__original_language
        media_language = self.__media_language()
        if language and any(stream.language.alpha3 == language.alpha3 for stream in self.audio_streams):
            logger.debug("%s - original language %s from TMDB", self.title, language)
            # TMDB has no country. The media can have one, for example en-US.
            if media_language and media_language.alpha3 == language.alpha3:
                return media_language
            return language

        return media_language

    def __media_language(self) -> babelfish.Language | None:
        languages = [
            stream.language
            for stream in sorted(self.video_streams, key=lambda x: x.default, reverse=True)
            if stream.language
        ]

        if languages:
            return languages[0]

        languages = [
            stream.language
            for stream in sorted(self.audio_streams, key=lambda x: x.default, reverse=True)
            if stream.language
        ]

        if languages:
            return languages[0]

        return None

    @property
    def selected_subtitle(self) -> Stream | None:
        streams = [stream for stream in self.subtitle_streams if stream.selected]
        return streams[0] if streams else None

    def select_audio(self, selection: Stream) -> None:
        audio_stream = selection.audio_stream
        if audio_stream is not None:
            self.part.setSelectedAudioStream(audio_stream)

    def unselect_subtitle(self) -> None:
        self.part.resetSelectedSubtitleStream()

    def select_subtitle(self, selection: Stream) -> None:
        subtitle_stream = selection.subtitle_stream
        if subtitle_stream is not None:
            self.part.setSelectedSubtitleStream(subtitle_stream)

    def choose_audio_track(self, preferences: Preferences) -> Stream | None:
        if preferences.keep_selected_audio:
            return self.selected_audio

        target_language = (
            preferences.language
            if (preferences.watching_preference == WatchingPreference.DUBBED)
            else self.original_language
        )
        language_cmp = VideoPart.__get_lang_cmp(target_language)

        streams = sorted(
            [
                audio
                for audio in self.audio_streams
                if (not preferences.audio_codecs or audio.codec in preferences.audio_codecs)
                and audio.codec not in preferences.excluded_audio_codecs
            ],
            key=functools.cmp_to_key(language_cmp),
        )

        return streams[0] if streams else self.selected_audio

    def choose_subtitle_track(self, preferences: Preferences) -> Stream | None:
        language_cmp = VideoPart.__get_lang_cmp(preferences.language)

        streams = sorted(
            [
                subtitle
                for subtitle in self.subtitle_streams
                if (not preferences.subtitle_codecs or subtitle.codec in preferences.subtitle_codecs)
                and subtitle.codec not in preferences.excluded_subtitle_codecs
            ],
            key=functools.cmp_to_key(language_cmp),
        )

        return streams[0] if streams else self.selected_subtitle

    def save_preferences(self, preferences: Preferences) -> Change | None:
        previous_selected_audio = self.selected_audio
        previous_selected_subtitle = self.selected_subtitle

        selected_audio = self.choose_audio_track(preferences)
        if selected_audio is not None and selected_audio != previous_selected_audio:
            logger.debug("%s - new audio track in %s selected: %s", self.title, selected_audio.language, selected_audio)
            self.select_audio(selected_audio)

        selected_audio_lang = selected_audio.language if selected_audio else None
        selected_subtitle = previous_selected_subtitle
        if preferences.keep_selected_subtitle and selected_subtitle:
            pass
        elif selected_audio_lang != preferences.language or preferences.force_subtitles:
            selected_subtitle = self.choose_subtitle_track(preferences)
            if selected_subtitle is not None and selected_subtitle != previous_selected_subtitle:
                logger.debug(
                    "%s new subtitle in %s selected: %s", self.title, selected_subtitle.language, selected_subtitle
                )
                self.select_subtitle(selected_subtitle)
        elif previous_selected_subtitle:
            logger.debug("%s - no subtitle selected", self.title)
            self.unselect_subtitle()
            selected_subtitle = None

        if selected_audio != previous_selected_audio or selected_subtitle != previous_selected_subtitle:
            return Change(self, previous_selected_audio, previous_selected_subtitle, selected_audio, selected_subtitle)

        return None

    def __str__(self) -> str:
        return f"{self.title}"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} - {self.title}]>"


class Change:
    def __init__(
        self,
        video: VideoPart,
        previous_audio: Stream | None,
        previous_subtitle: Stream | None,
        audio: Stream | None,
        subtitle: Stream | None,
    ):
        self.video = video
        self.previous_audio = previous_audio
        self.previous_subtitle = previous_subtitle
        self.audio = audio
        self.subtitle = subtitle

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} - {self.video}]>"


class Plex:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._plex: plexapi.server.PlexServer | None = None
        self.original_languages: OriginalLanguages | None = None
        if settings.tmdb_key:
            cache_path = os.path.join(settings.cache_dir, "original_languages.jsonl") if settings.cache_dir else None
            self.original_languages = OriginalLanguages(settings.tmdb_key, cache_path)

    @property
    def server(self) -> plexapi.server.PlexServer:
        if self._plex is None:
            logger.debug("Connected to %s", self.settings.url)
            self._plex = plexapi.server.PlexServer(baseurl=self.settings.url, token=self.settings.token)
        return self._plex

    def __find_sections(self, criteria: Criteria) -> list[plexapi.library.LibrarySection]:
        if not criteria.libraries:
            return typing.cast("list[plexapi.library.LibrarySection]", self.server.library.sections())

        sections: list[plexapi.library.LibrarySection] = []
        for library in criteria.libraries:
            sections.append(self.server.library.section(library))

        return sections

    def search(self, criteria: Criteria) -> list[Video]:
        sections = self.__find_sections(criteria)
        logger.debug("Found %d sections", len(sections))
        results: list[Video] = []
        for section in sections:
            logger.debug("Entering section %s", section.title)
            if section.type == "show":
                filters_list = criteria.to_filters(LibraryType.EPISODE)
                for filters in filters_list:
                    episodes: list[plexapi.video.Episode] = section.all(libtype="episode", filters=filters)
                    logger.debug("Found %d episodes in section %s", len(episodes), section.title)
                    results.extend([Video(e) for e in episodes if Video.accept(e, criteria)])

            if section.type == "movie":
                filters_list = criteria.to_filters(LibraryType.MOVIE)
                for filters in filters_list:
                    movies: list[plexapi.video.Movie] = section.all(libtype="movie", filters=filters)
                    logger.debug("Found %d movies in section %s", len(movies), section.title)
                    results.extend([Video(m) for m in movies if Video.accept(m, criteria)])

        return results
