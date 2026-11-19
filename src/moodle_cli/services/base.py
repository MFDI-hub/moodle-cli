"""Shared service helpers for Moodle web-service wrappers."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

__all__ = ["BaseService", "MoodleCaller", "MoodleModel"]


class MoodleCaller(Protocol):
    """Minimal client interface used by service wrappers."""

    base_url: str
    token: str
    session: Any

    def call(self, wsfunction: str, **params: Any) -> Any:
        """Invoke a Moodle web-service function and return the parsed payload."""
        ...


class MoodleModel(BaseModel):
    """Pydantic model that accepts Moodle's wire names and Python snake_case."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class BaseService:
    """Thin wrapper around a Moodle HTTP or session client."""

    def __init__(self, client: MoodleCaller) -> None:
        self.client = client

    def call(self, wsfunction: str, **params: Any) -> Any:
        """Forward a web-service call through the bound client."""
        return self.client.call(wsfunction, **params)
