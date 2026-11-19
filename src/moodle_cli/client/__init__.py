"""Moodle HTTP client and exceptions."""

from moodle_cli.client.exceptions import (
    AuthenticationError,
    ConfigError,
    ConnectionError,
    MoodleAPIError,
    MoodleConnectionError,
    MoodleError,
    ProfileNotFoundError,
    ReadOnlyViolation,
)
from moodle_cli.client.http import MoodleHTTPClient

__all__ = [
    "AuthenticationError",
    "ConfigError",
    "ConnectionError",
    "MoodleAPIError",
    "MoodleConnectionError",
    "MoodleError",
    "MoodleHTTPClient",
    "ProfileNotFoundError",
    "ReadOnlyViolation",
]
