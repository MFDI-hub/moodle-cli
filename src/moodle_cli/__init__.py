# Copyright (C) 2026 Marc Alier, Juanan Pereira — LAMB Project
# SPDX-License-Identifier: GPL-3.0-or-later

"""moodle-cli — a Python library and CLI for Moodle Web Services.

The supported import surface is :class:`~moodle_cli.api.Moodle` plus the
exception types in ``__all__``. Subpackages are implementation details.
"""

from __future__ import annotations

import logging
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from typing import Any

logging.getLogger("moodle_cli").addHandler(logging.NullHandler())

try:
    __version__ = version("moodle-cli")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.1.0"

__all__ = [
    "AuthenticationError",
    "ConfigError",
    "Moodle",
    "MoodleAPIError",
    "MoodleConnectionError",
    "MoodleError",
    "ProfileNotFoundError",
    "ReadOnlyViolation",
    "__version__",
]

_LAZY_ATTRS: dict[str, tuple[str, str]] = {
    "Moodle": ("moodle_cli.api", "Moodle"),
    "AuthenticationError": ("moodle_cli.exceptions", "AuthenticationError"),
    "ConfigError": ("moodle_cli.exceptions", "ConfigError"),
    "ConnectionError": ("moodle_cli.exceptions", "ConnectionError"),
    "MoodleAPIError": ("moodle_cli.exceptions", "MoodleAPIError"),
    "MoodleConnectionError": ("moodle_cli.exceptions", "MoodleConnectionError"),
    "MoodleError": ("moodle_cli.exceptions", "MoodleError"),
    "ProfileNotFoundError": ("moodle_cli.exceptions", "ProfileNotFoundError"),
    "ReadOnlyViolation": ("moodle_cli.exceptions", "ReadOnlyViolation"),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr = _LAZY_ATTRS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    return getattr(import_module(module_name), attr)


def __dir__() -> list[str]:
    return sorted({*globals().keys(), *__all__})
