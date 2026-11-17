"""Placeholder tests.

Delete these once you have real tests; they exist so that a freshly generated
project passes `make test` including its coverage gate.
"""

from __future__ import annotations

import moodle_cli
from moodle_cli import moodle_cli as cli


def test_version_is_a_string() -> None:
    assert isinstance(moodle_cli.__version__, str)


def test_main_runs() -> None:
    assert cli.main() is None


def test_python_m_entrypoint() -> None:
    import importlib

    entry = importlib.import_module("moodle_cli.__main__")
    assert entry.main is cli.main
