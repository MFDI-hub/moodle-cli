"""Output rendering utilities."""

from moodle_cli.output.console import console, error_console
from moodle_cli.output.encode import machine_format, write_machine
from moodle_cli.output.format import ago, fmt_ts, trim
from moodle_cli.output.json import render_json
from moodle_cli.output.style import output_quiet
from moodle_cli.output.tables import render_table

__all__ = [
    "ago",
    "console",
    "error_console",
    "fmt_ts",
    "machine_format",
    "render_json",
    "render_table",
    "status",
    "trim",
    "write_machine",
]


def status(message: str) -> None:
    """Incidental progress line. Hidden by --quiet. Results still print."""
    if not output_quiet.get():
        console.print(message)
