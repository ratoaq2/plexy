from importlib import metadata

__title__ = metadata.metadata(__package__)['name']
__version__ = metadata.version(__package__)
__short_version__ = '.'.join(__version__.split('.')[:2])
__author__ = metadata.metadata(__package__)['author']
__license__ = metadata.metadata(__package__)['license']
__url__ = 'https://github.com/ratoaq2/plexy'

del metadata

from .api import (
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
)
