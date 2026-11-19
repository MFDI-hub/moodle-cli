"""JSON output renderer (also YAML and CSV when those formats are selected)."""

from __future__ import annotations

from typing import Any

from moodle_cli.output.encode import write_machine


def render_json(data: Any) -> None:
    """Write machine-readable output to stdout."""
    write_machine(data)
