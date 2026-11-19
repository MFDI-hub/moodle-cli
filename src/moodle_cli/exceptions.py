"""Public exception types for moodle-cli."""

from __future__ import annotations

from typing import ClassVar


class MoodleError(Exception):
    """Base exception for all Moodle errors."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        self.error_code = error_code
        super().__init__(message)


class MoodleAPIError(MoodleError):
    """Error returned by the Moodle Web Services API."""

    HINTS: ClassVar[dict[str, str]] = {
        "invalidtoken": "Your token is invalid or expired. Run: moodle auth login",
        "accessexception": "You don't have permission for this operation.",
        "invalidparameter": "One or more parameters are invalid.",
        "invalidrecord": "The requested record does not exist.",
        "webservicenotavailable": "This web service function is not enabled on the site.",
        "nopermissions": "You don't have the required capability.",
        "sitenotfound": "The Moodle site could not be reached.",
        "invalidresponse": "Unexpected response format from Moodle.",
        "servicenotavailable": "External services are disabled on this site.",
        "forabortedreason": "The operation was aborted by the server.",
    }

    def __init__(
        self, message: str, error_code: str | None = None, debug_info: str | None = None
    ) -> None:
        self.debug_info = debug_info
        super().__init__(message, error_code)

    @property
    def hint(self) -> str | None:
        """Human-readable recovery hint for a known Moodle ``errorcode``."""
        if self.error_code:
            return self.HINTS.get(self.error_code)
        return None


class AuthenticationError(MoodleError):
    """Failed to authenticate with Moodle."""


class MoodleConnectionError(MoodleError):
    """Failed to connect to the Moodle instance."""


ConnectionError = MoodleConnectionError


class ReadOnlyViolation(MoodleError):
    """A write operation was attempted through a read-only client.

    Raised by MoodleHTTPClient.call when running in read-only mode and the
    requested wsfunction is not in client.readonly.READ_ALLOWLIST.
    """


class ConfigError(MoodleError):
    """Configuration file error."""


class ProfileNotFoundError(ConfigError):
    """Requested profile does not exist."""


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
