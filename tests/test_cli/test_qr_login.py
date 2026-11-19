"""Tests for the `auth qr-login` CLI command (isolated from real config/keyring)."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from moodle_cli.cli.main import cli
from tests.http_mock import Response, Router

SITE = "https://moodle.example.com"
AJAX = f"{SITE}/lib/ajax/service-nologin.php"
REST = f"{SITE}/webservice/rest/server.php"


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect config to a tmp file and the keyring to an in-memory dict."""
    from moodle_cli.config import auth as authmod, manager as mgr

    monkeypatch.setattr(mgr, "DEFAULT_CONFIG_FILE", tmp_path / "config.toml")

    store: dict[tuple[str, str], str] = {}

    class FakeKeyring:
        class errors:
            class PasswordDeleteError(Exception):
                pass

        def set_password(self, service: str, key: str, value: str) -> None:
            store[(service, key)] = value

        def get_password(self, service: str, key: str) -> str | None:
            return store.get((service, key))

        def delete_password(self, service: str, key: str) -> None:
            store.pop((service, key), None)

    monkeypatch.setattr(authmod, "keyring", FakeKeyring())


def test_qr_login_with_uri(isolated: None, mock_http: Router) -> None:
    mock_http.post(AJAX).mock(
        return_value=Response(200, json=[{"error": False, "data": {"token": "TOK"}}])
    )
    mock_http.post(REST).mock(
        return_value=Response(
            200, json={"username": "marc.alier", "sitename": "Demo", "release": "4.5"}
        )
    )
    result = CliRunner().invoke(
        cli,
        [
            "auth",
            "qr-login",
            "moodlemobile://https://moodle.example.com?qrlogin=freshkey&userid=42",
            "--name",
            "demo",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Logged in as marc.alier" in result.output
    assert "Demo" in result.output


def test_qr_login_expired_key(isolated: None, mock_http: Router) -> None:
    mock_http.post(AJAX).mock(
        return_value=Response(
            200,
            json=[
                {"error": True, "exception": {"errorcode": "invalidkey", "message": "Invalid key"}}
            ],
        )
    )
    result = CliRunner().invoke(
        cli,
        [
            "auth",
            "qr-login",
            "moodlemobile://https://moodle.example.com?qrlogin=dead&userid=42",
            "--name",
            "demo",
        ],
    )
    assert result.exit_code == 1
    assert "single-use" in result.output


def test_qr_login_requires_input(isolated: None) -> None:
    result = CliRunner().invoke(cli, ["auth", "qr-login"])
    assert result.exit_code != 0
    assert "Provide the QR" in result.output


def test_qr_login_username_override_skips_siteinfo(isolated: None, mock_http: Router) -> None:
    # No REST mock registered: passing --username must avoid the site-info call.
    mock_http.post(AJAX).mock(
        return_value=Response(200, json=[{"error": False, "data": {"token": "TOK"}}])
    )
    result = CliRunner().invoke(
        cli,
        [
            "auth",
            "qr-login",
            "--url",
            SITE,
            "--key",
            "k",
            "--userid",
            "42",
            "--username",
            "preset",
            "--name",
            "demo",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Logged in as preset" in result.output
