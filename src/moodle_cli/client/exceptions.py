"""Compatibility re-exports. Prefer :mod:`moodle_cli.exceptions`."""

from moodle_cli.exceptions import (
    AuthenticationError,
    ConfigError,
    ConnectionError,
    MoodleAPIError,
    MoodleConnectionError,
    MoodleError,
    ProfileNotFoundError,
    ReadOnlyViolation,
)

__all__ = [
    "AuthenticationError",
    "ConfigError",
    "ConnectionError",
    "MoodleAPIError",
    "MoodleConnectionError",
    "MoodleError",
    "ProfileNotFoundError",
    "ReadOnlyViolation",
]
