"""A fake TMDB API for tests: a requests.Session that gives the original language and records the requests.

See docs/testing.md.
"""

import json
import typing

import requests

from plexy.original_language import TMDB_URL

# A language code (or None) gives a 200 answer. A number gives that status. An exception is raised.
Answer = str | None | int | Exception


class Request(typing.NamedTuple):
    path: str
    headers: dict[str, str]
    params: dict[str, str]


class FakeTmdb(requests.Session):
    def __init__(self, answers: dict[str, Answer] | None = None) -> None:
        """`answers` has one answer for each `movie/<id>` or `tv/<id>`. Other paths give 404."""
        super().__init__()
        self.answers = answers or {}
        self.requests: list[Request] = []

    @property
    def paths(self) -> list[str]:
        return [r.path for r in self.requests]

    def get(self, url: str | bytes, **kwargs: typing.Any) -> requests.Response:
        path = str(url).removeprefix(f"{TMDB_URL}/")
        self.requests.append(Request(path, dict(kwargs.get("headers") or {}), dict(kwargs.get("params") or {})))
        answer = self.answers.get(path, 404)
        if isinstance(answer, Exception):
            raise answer

        response = requests.Response()
        response.url = str(url)
        response.status_code = answer if isinstance(answer, int) else 200
        body = {"original_language": answer} if not isinstance(answer, int) else {"status_code": 34}
        response._content = json.dumps(body).encode("utf-8")
        return response
