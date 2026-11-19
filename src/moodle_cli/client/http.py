"""Core HTTP client for Moodle Web Services REST API."""

from __future__ import annotations

import logging
from typing import Any

from curl_cffi import Session
from curl_cffi.requests.exceptions import HTTPError, RequestException

from moodle_cli._utils import redact
from moodle_cli.client.readonly import READ_ALLOWLIST
from moodle_cli.exceptions import (
    AuthenticationError,
    MoodleAPIError,
    MoodleConnectionError,
    ReadOnlyViolation,
)

logger = logging.getLogger(__name__)


def flatten_params(params: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Flatten nested dicts/lists into Moodle's bracket-notation parameters.

    Example: {"courses": [{"id": 1}]} → {"courses[0][id]": "1"}
    """
    flat: dict[str, str] = {}
    for key, value in params.items():
        full_key = f"{prefix}[{key}]" if prefix else key
        if isinstance(value, dict):
            flat.update(flatten_params(value, full_key))
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                idx_key = f"{full_key}[{i}]"
                if isinstance(item, dict):
                    flat.update(flatten_params(item, idx_key))
                else:
                    flat[idx_key] = str(item)
        elif isinstance(value, bool):
            flat[full_key] = "1" if value else "0"
        elif value is not None:
            flat[full_key] = str(value)
    return flat


class MoodleHTTPClient:
    """HTTP client for Moodle Web Services.

    Token REST calls go to ``/webservice/rest/server.php``. Diagnostic detail is
    emitted with :mod:`logging`; the CLI turns that on via ``--verbose``.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        service: str = "moodle_mobile_app",
        timeout: float = 30.0,
        readonly: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.service = service
        self.readonly = readonly
        self.verbose = False
        self.session = Session(impersonate="firefox155", timeout=timeout)

    @property
    def rest_url(self) -> str:
        return f"{self.base_url}/webservice/rest/server.php"

    def call(self, wsfunction: str, **params: Any) -> Any:
        """Call a Moodle Web Services function.

        Returns the parsed JSON response (dict or list).
        Raises MoodleAPIError on Moodle-level errors.
        Raises ReadOnlyViolation if readonly and wsfunction is not read-allowlisted.
        """
        if self.readonly and wsfunction not in READ_ALLOWLIST:
            raise ReadOnlyViolation(
                f"Read-only mode: web-service function '{wsfunction}' is not in the read "
                f"allowlist. moodle-readonly refuses any operation that could mutate the site."
            )

        flat = flatten_params(params)
        flat["wstoken"] = self.token
        flat["wsfunction"] = wsfunction
        flat["moodlewsrestformat"] = "json"

        logger.debug("POST %s %s", wsfunction, redact(flat))

        try:
            resp = self.session.post(self.rest_url, data=flat)
            resp.raise_for_status()
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "error"
            raise MoodleConnectionError(f"HTTP {status} from {self.base_url}") from exc
        except RequestException as exc:
            raise MoodleConnectionError(f"Could not connect to {self.base_url}: {exc}") from exc

        data = resp.json()

        if isinstance(data, dict) and "exception" in data:
            raise MoodleAPIError(
                message=data.get("message", "Unknown Moodle error"),
                error_code=data.get("errorcode"),
                debug_info=data.get("debuginfo"),
            )

        return data

    @staticmethod
    def authenticate(
        base_url: str, username: str, password: str, service: str = "moodle_mobile_app"
    ) -> str:
        """Authenticate and return a token.

        Posts to /login/token.php and returns the token string.
        """
        url = f"{base_url.rstrip('/')}/login/token.php"
        try:
            with Session(impersonate="firefox155", timeout=30.0) as session:
                resp = session.post(
                    url,
                    data={
                        "username": username,
                        "password": password,
                        "service": service,
                    },
                )
                resp.raise_for_status()
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "error"
            raise MoodleConnectionError(f"HTTP {status} from {base_url}") from exc
        except RequestException as exc:
            raise MoodleConnectionError(f"Could not connect to {base_url}: {exc}") from exc

        data = resp.json()
        if "token" in data:
            return data["token"]

        error = data.get("error", "Authentication failed")
        raise AuthenticationError(error, error_code=data.get("errorcode"))

    def close(self) -> None:
        """Release the underlying HTTP session."""
        self.session.close()

    def __enter__(self) -> MoodleHTTPClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
