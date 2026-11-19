"""Shared test fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from moodle_cli.client.http import MoodleHTTPClient
from tests.http_mock import Router

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "responses"

BASE_URL = "https://moodle.example.com"
TOKEN = "test-token-abc123"


@pytest.fixture(autouse=True)
def isolate_cli_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep CLI tests off the real config file and OS keyring."""
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


def load_fixture(name: str) -> Any:
    with open(FIXTURES_DIR / f"{name}.json") as f:
        return json.load(f)


@pytest.fixture
def client() -> MoodleHTTPClient:
    return MoodleHTTPClient(base_url=BASE_URL, token=TOKEN)


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def mock_http(monkeypatch: pytest.MonkeyPatch) -> Router:
    """Patch curl_cffi Session.post and return a router for canned responses."""
    from curl_cffi import Session

    router = Router()

    def fake_post(
        self: Session,
        url: str,
        data: Any = None,
        json: Any = None,
        headers: dict[str, str] | None = None,
        **kwargs: Any,
    ) -> Any:
        return router.dispatch(url, data=data, json=json, headers=headers)

    monkeypatch.setattr(Session, "post", fake_post)
    return router
