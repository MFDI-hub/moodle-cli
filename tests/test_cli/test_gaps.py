"""CLI coverage for the non-moosh gap commands."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from click.testing import CliRunner

from moodle_cli._utils import redact
from moodle_cli.cli.main import cli
from moodle_cli.cli.readonly import cli_readonly
from moodle_cli.output.encode import write_machine
from moodle_cli.output.style import output_fields, output_format

if TYPE_CHECKING:
    import pytest


def test_help_lists_new_commands() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["course", "--help"])
    assert result.exit_code == 0
    for name in ("sync", "ensure", "duplicate", "backup", "section", "categories", "module"):
        assert name in result.output


def test_nested_category_writes_absent_from_readonly() -> None:
    runner = CliRunner()
    result = runner.invoke(cli_readonly, ["course", "categories", "create", "--help"])
    assert result.exit_code != 0


def test_readonly_keeps_module_show() -> None:
    runner = CliRunner()
    result = runner.invoke(cli_readonly, ["course", "module", "--help"])
    assert result.exit_code == 0
    assert "show" in result.output
    assert "add" not in result.output


def test_dry_run_course_create_does_not_need_login() -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--dry-run",
            "--json",
            "course",
            "create",
            "--fullname",
            "A",
            "--shortname",
            "A",
            "--categoryid",
            "1",
        ],
    )
    assert result.exit_code == 0
    assert "core_course_create_courses" in result.output
    assert "dry_run" in result.output


def test_yaml_output(capsys: pytest.CaptureFixture[str]) -> None:
    output_format.set("yaml")
    output_fields.set(None)
    write_machine([{"ID": 1, "Name": "Math"}])
    captured = capsys.readouterr()
    assert "ID: 1" in captured.out
    assert "Name: Math" in captured.out
    output_format.set("table")


def test_csv_fields(capsys: pytest.CaptureFixture[str]) -> None:
    output_format.set("csv")
    output_fields.set(["Name"])
    write_machine([{"ID": 1, "Name": "Math"}])
    captured = capsys.readouterr()
    assert "Name" in captured.out
    assert "Math" in captured.out
    assert "ID" not in captured.out.splitlines()[0]
    output_format.set("table")
    output_fields.set(None)


def test_redact_hides_tokens() -> None:
    hidden = redact({"wstoken": "secret", "sesskey": "abc", "courseid": 4})
    assert hidden["wstoken"] == "***"
    assert hidden["sesskey"] == "***"
    assert hidden["courseid"] == 4


def test_moodle_profile_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOODLE_PROFILE", "staging")
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert os.environ["MOODLE_PROFILE"] == "staging"


def test_completion_script() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["completion", "script", "bash"])
    assert result.exit_code == 0
    assert "moodle" in result.output.lower() or "complete" in result.output.lower()
