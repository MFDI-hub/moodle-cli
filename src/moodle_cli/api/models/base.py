"""Shared dataclass helpers for Moodle objects.

:class:`Remote` is the base for every live object bound to a :class:`~moodle_cli.api.Moodle`
session. Nested payloads are converted with :meth:`Remote.to_dict`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from moodle_cli._utils import safe_name

if TYPE_CHECKING:
    from moodle_cli.api.moodle import Moodle

__all__ = ["Remote", "safe_name"]


def _jsonable(value: Any) -> Any:
    if isinstance(value, Remote):
        return value.to_dict()
    if is_dataclass(value) and not isinstance(value, type):
        return {
            item.name: _jsonable(getattr(value, item.name))
            for item in fields(value)
            if not item.name.startswith("_")
        }
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Path):
        return str(value)
    return value


@dataclass
class Remote:
    """Object bound to a live Moodle session. Fields starting with ``_`` stay private."""

    _api: Moodle = field(repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for item in fields(self):
            if item.name.startswith("_"):
                continue
            data[item.name] = _jsonable(getattr(self, item.name))
        return data
