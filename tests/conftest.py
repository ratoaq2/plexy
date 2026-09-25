import os
import typing
import xml.etree.ElementTree as ET

import plexapi.server
import pytest

from tests.fakeplex import FakePlex

URL = "http://plex.test:32400"


@pytest.fixture
def fake_plex(monkeypatch: pytest.MonkeyPatch) -> typing.Callable[..., FakePlex]:
    """Return a function that loads a scenario (or builder items) and makes plexy use it as the Plex server."""

    def install(scenario: str | None = None, items: list[ET.Element] | None = None) -> FakePlex:
        fake = FakePlex.from_folder(scenario) if scenario else FakePlex.from_items(items or [])
        init = plexapi.server.PlexServer.__init__

        def fake_init(self: plexapi.server.PlexServer, baseurl: str, token: str, **kwargs: typing.Any) -> None:
            init(self, baseurl, token, session=fake)

        monkeypatch.setattr(plexapi.server.PlexServer, "__init__", fake_init)
        return fake

    return install


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip the live tests when PLEXY_TEST_CONFIG is not set. See docs/testing.md."""
    if os.environ.get("PLEXY_TEST_CONFIG"):
        return
    skip = pytest.mark.skip(reason="PLEXY_TEST_CONFIG is not set")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
