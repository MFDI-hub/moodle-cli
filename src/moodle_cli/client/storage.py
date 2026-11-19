"""Load a Playwright storage-state file saved by a logged-in browser."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    from pathlib import Path

from moodle_cli.exceptions import AuthenticationError


def load_storage_state(path: Path) -> dict[str, Any]:
    """Read a storage-state JSON file."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuthenticationError(f"Could not read storage state {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise AuthenticationError(f"Storage state {path} is not a JSON object.")
    return data


def site_url_from_storage(path: Path) -> str:
    """Return ``https://host`` for the MoodleSession cookie in a storage-state file."""
    for cookie in load_storage_state(path).get("cookies") or []:
        if cookie.get("name") == "MoodleSession" and cookie.get("domain"):
            return "https://" + str(cookie["domain"]).lstrip(".")
    raise AuthenticationError(
        f"No MoodleSession cookie in {path}. Save a session after signing in."
    )


def cookies_for_host(path: Path, base_url: str) -> list[dict[str, Any]]:
    """Cookies in the storage state whose domain matches ``base_url``."""
    host = urlparse(base_url).netloc.casefold()
    matched: list[dict[str, Any]] = []
    for cookie in load_storage_state(path).get("cookies") or []:
        domain = str(cookie.get("domain", "")).lstrip(".").casefold()
        if domain and (domain == host or host.endswith("." + domain)):
            matched.append(cookie)
    if not matched:
        raise AuthenticationError(f"Storage state {path} has no cookies for {host}.")
    return matched
