"""Click command-line interface for moodle-cli."""

from __future__ import annotations

from typing import Any

__all__ = ["cli", "cli_readonly", "main"]


def __getattr__(name: str) -> Any:
    if name in {"cli", "main"}:
        from moodle_cli.cli.main import cli, main

        return cli if name == "cli" else main
    if name == "cli_readonly":
        from moodle_cli.cli.readonly import cli_readonly

        return cli_readonly
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
