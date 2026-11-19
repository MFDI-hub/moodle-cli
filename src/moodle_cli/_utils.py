"""Private helpers shared by the CLI, HTTP client, and services."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlparse, urlsplit

from moodle_cli.exceptions import MoodleError

if TYPE_CHECKING:
    from moodle_cli.client.session import MoodleSessionClient
    from moodle_cli.services.base import MoodleCaller

_SECRET_HINTS = ("token", "password", "sesskey", "secret", "passwd", "privatetoken")
_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(name: str) -> str:
    """Replace characters that cannot appear in a file name."""
    name = _UNSAFE.sub("_", name).strip(" .")
    return name or "file"


def file_save_name(name: str, url: str = "") -> str:
    """Prefer the URL basename (real Moodle filename) over link text."""
    last = unquote(urlsplit(url).path.rstrip("/").split("/")[-1]) if url else ""
    if last and Path(last).suffix:
        return safe_name(last)
    return safe_name(name or last or "file")


def redact(value: Any) -> Any:
    """Copy nested params with tokens, passwords, and sesskeys replaced."""
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if any(hint in lowered for hint in _SECRET_HINTS):
                out[key] = "***"
            else:
                out[key] = redact(item)
        return out
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def require_session(client: MoodleCaller) -> MoodleSessionClient:
    """Raise a clear error when a command needs cookies instead of a token."""
    from moodle_cli.client.session import MoodleSessionClient

    if isinstance(client, MoodleSessionClient):
        return client
    raise MoodleError(
        "This command needs a browser session. Run: "
        "moodle auth session --storage-state FILE --name PROFILE"
    )


def parse_fields(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    fields = [part.strip() for part in raw.split(",") if part.strip()]
    return fields or None


def parse_customfields(pairs: tuple[str, ...]) -> list[dict[str, str]]:
    """Turn repeated --customfield shortname=value flags into Moodle customfields."""
    fields: list[dict[str, str]] = []
    for pair in pairs:
        if "=" not in pair:
            raise MoodleError(f"Custom field must be shortname=value, got {pair!r}")
        short_name, value = pair.split("=", 1)
        fields.append({"shortname": short_name, "value": value})
    return fields


def host_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower()
