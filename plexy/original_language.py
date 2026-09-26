"""The original language of a movie or show, from TMDB. See docs/stream-selection.md."""

from __future__ import annotations

import json
import logging
import os

import babelfish
import plexapi.video
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

TMDB_URL = "https://api.themoviedb.org/3"


class TmdbError(Exception):
    pass


def tmdb_session() -> requests.Session:
    """Return a session that waits and sends the request again when TMDB answers 429 (too many requests)."""
    # No retry on connection errors: urllib3 logs them with the URL, and a v3 key is in the URL.
    retry = Retry(connect=0, read=0, other=0, status=5, status_forcelist=[429], backoff_factor=1)
    session = requests.Session()
    session.mount(TMDB_URL, HTTPAdapter(max_retries=retry))
    return session


class OriginalLanguages:
    """Find the original language with the `tmdb://` guid of the movie or show.

    The TMDB answers go to a JSON lines file, with the Plex guid as the key. A later run reads them and sends no
    request. Errors do not go to the file.
    """

    def __init__(self, tmdb_key: str, cache_path: str | None, session: requests.Session | None = None):
        self.tmdb_key = tmdb_key
        self.cache_path = cache_path
        self.session = session or tmdb_session()
        self.cache = self.__read_cache()
        self.languages: dict[str, babelfish.Language | None] = {}
        self.enabled = True

    def __read_cache(self) -> dict[str, str | None]:
        cache: dict[str, str | None] = {}
        if not self.cache_path or not os.path.isfile(self.cache_path):
            return cache

        with open(self.cache_path, encoding="utf-8") as f:
            for line in f:
                try:
                    cache.update(json.loads(line))
                except ValueError:
                    logger.debug("Ignoring an invalid line in %s", self.cache_path)
        return cache

    def __write_cache(self, key: str, code: str | None) -> None:
        self.cache[key] = code
        if not self.cache_path:
            return

        os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
        with open(self.cache_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({key: code}) + "\n")

    def get(self, video: plexapi.video.Movie | plexapi.video.Episode) -> babelfish.Language | None:
        episode = isinstance(video, plexapi.video.Episode)
        key: str | None = video.grandparentGuid if episode else video.guid
        if not key:
            return None
        if key not in self.languages:
            self.languages[key] = self.__find(video, key, "tv" if episode else "movie")
        return self.languages[key]

    def __find(
        self, video: plexapi.video.Movie | plexapi.video.Episode, key: str, kind: str
    ) -> babelfish.Language | None:
        if key in self.cache:
            logger.debug("TMDB language for %s is in the cache", key)
            return self.__to_language(self.cache[key])
        if not self.enabled:
            return None

        guids = video.show().guids if isinstance(video, plexapi.video.Episode) else video.guids
        tmdb_id = next((guid.id[len("tmdb://") :] for guid in guids if guid.id.startswith("tmdb://")), None)
        if tmdb_id is None:
            logger.debug("No TMDB guid for %s", key)
            return None

        try:
            code = self.__request(kind, tmdb_id)
        except TmdbError as error:
            logger.warning("TMDB request for %s %s failed: %s", kind, tmdb_id, error)
            return None

        self.__write_cache(key, code)
        return self.__to_language(code)

    def __request(self, kind: str, tmdb_id: str) -> str | None:
        """Return the TMDB language code. The errors never show the URL, because it can have the key."""
        # a v4 read access token is a JWT, a v3 key is a short hex string
        bearer = self.tmdb_key.startswith("eyJ")
        headers = {"Authorization": f"Bearer {self.tmdb_key}"} if bearer else {}
        params = {} if bearer else {"api_key": self.tmdb_key}
        try:
            response = self.session.get(f"{TMDB_URL}/{kind}/{tmdb_id}", headers=headers, params=params, timeout=10)
            if response.status_code == 404:
                raise TmdbError("not found")
            if not response.ok:
                self.enabled = False
                raise TmdbError(f"status {response.status_code}. TMDB is not used again in this run")
            code: str | None = response.json().get("original_language")
        except requests.RequestException as error:
            self.enabled = False
            raise TmdbError(f"{type(error).__name__}. TMDB is not used again in this run") from None

        logger.debug("TMDB language for %s %s is %s", kind, tmdb_id, code)
        return code

    @staticmethod
    def __to_language(code: str | None) -> babelfish.Language | None:
        if not code:
            return None
        try:
            return babelfish.Language.fromalpha2(code)
        except (babelfish.Error, ValueError, KeyError):
            # TMDB has codes that are not ISO 639-1, for example xx (no language) and cn (Cantonese)
            logger.debug("TMDB language %s is not known", code)
            return None
