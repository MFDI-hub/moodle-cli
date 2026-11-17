# Copyright (C) 2026 Marc Alier, Juanan Pereira — LAMB Project
# SPDX-License-Identifier: GPL-3.0-or-later

"""moodle-cli — A Python CLI for Moodle Web Services."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("moodle-cli")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.1.0"

__all__ = ["__version__"]
