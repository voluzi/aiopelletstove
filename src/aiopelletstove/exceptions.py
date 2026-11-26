"""Errors raised by the register protocol client."""


class PelletStoveError(Exception):
    """Base protocol error."""


class PelletStoveConnectionError(PelletStoveError):
    """Transport failure or timeout."""


class PelletStoveResponseError(PelletStoveError):
    """Malformed, incomplete, or rejected device response."""


class PelletStoveRejectedError(PelletStoveResponseError):
    """The device answered with an explicit rejection."""


class PelletStovePowerOutcomeUnknownError(PelletStoveError):
    """A power toggle was sent but its acknowledgement was lost or unreadable.

    The stove may still act on it. Do not send another toggle until the stove
    reports a power state that settles the outcome.
    """


class PelletStoveReadOnlyError(PelletStoveError):
    """Attempt to write a read-only register."""


class PelletStoveValueError(PelletStoveError, ValueError):
    """Unsupported or out-of-range input."""
