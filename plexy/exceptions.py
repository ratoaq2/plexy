class Error(Exception):
    """Base class for exceptions in plexy."""

    pass


class InvalidTitle(Error):
    """Exception raised when parsing Title."""

    pass


class PlexUserError(Error):
    """Exception raised when plexy cannot work as the Plex user of the settings."""

    pass
