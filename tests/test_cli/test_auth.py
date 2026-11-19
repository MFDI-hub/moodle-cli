"""Tests for auth CLI commands."""

from __future__ import annotations

from click.testing import CliRunner

from moodle_cli.cli.main import cli
from tests.http_mock import Response, Router

BASE_URL = "https://moodle.example.com"


class TestAuthLogin:
    def test_login_success(self, mock_http: Router, tmp_path: object) -> None:
        mock_http.post(f"{BASE_URL}/login/token.php").mock(
            return_value=Response(200, json={"token": "abc123"})
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "auth",
                "login",
                "--url",
                BASE_URL,
                "--username",
                "admin",
                "--password",
                "secret",
                "--profile-name",
                "test",
            ],
        )
        assert result.exit_code == 0
        assert "Logged in" in result.output

    def test_login_failure(self, mock_http: Router) -> None:
        mock_http.post(f"{BASE_URL}/login/token.php").mock(
            return_value=Response(
                200,
                json={
                    "error": "Invalid login",
                    "errorcode": "invalidlogin",
                },
            )
        )
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "auth",
                "login",
                "--url",
                BASE_URL,
                "--username",
                "admin",
                "--password",
                "wrong",
            ],
        )
        assert result.exit_code == 1


class TestAuthProfiles:
    def test_profiles_empty(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["auth", "profiles"])
        assert result.exit_code == 0
