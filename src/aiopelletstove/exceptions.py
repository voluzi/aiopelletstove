"""Errors raised by the register protocol client."""


class PelletStoveError(Exception):
    """Base protocol error."""


class PelletStoveConnectionError(PelletStoveError):
    """Transport failure or timeout."""


class PelletStoveResponseError(PelletStoveError):
    """Malformed, incomplete, or rejected device response."""


class PelletStoveReadOnlyError(PelletStoveError):
    """Attempt to write a read-only register."""


class PelletStoveValueError(PelletStoveError, ValueError):
    """Unsupported or out-of-range input."""
