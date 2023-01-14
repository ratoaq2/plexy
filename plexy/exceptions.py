class Error(Exception):
    """Base class for exceptions in plexy."""
    pass


class InvalidTitle(Error):
    """Exception raised when parsing Title."""
    pass
