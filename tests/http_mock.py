"""In-process stand-in for curl_cffi Session.post.

respx only hooks httpx. These tests patch Session.post and return canned JSON.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

if TYPE_CHECKING:
    from collections.abc import Generator

from curl_cffi import Session
from curl_cffi.requests.exceptions import HTTPError


class Response:
    """Minimal response with the .json() / .raise_for_status() surface the client uses."""

    def __init__(self, status_code: int, *, json: Any = None) -> None:
        self.status_code = status_code
        self._json = json

    def json(self) -> Any:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise HTTPError(f"HTTP Error {self.status_code}", response=self)


class _Headers(dict[str, str]):
    def __getitem__(self, key: str) -> str:
        for existing, value in self.items():
            if existing.lower() == key.lower():
                return value
        raise KeyError(key)


class _Request:
    def __init__(self, content: bytes, headers: dict[str, str]) -> None:
        self.content = content
        self.headers = _Headers(headers)


class _Call:
    def __init__(self, request: _Request) -> None:
        self.request = request


class _Calls:
    def __init__(self) -> None:
        self._items: list[_Call] = []

    def add(self, request: _Request) -> None:
        self._items.append(_Call(request))

    def __getitem__(self, index: int) -> _Call:
        return self._items[index]

    @property
    def last(self) -> _Call:
        return self._items[-1]


class Route:
    def __init__(self, url: str) -> None:
        self.url = url.split("?", 1)[0]
        self.calls = _Calls()
        self.return_value: Response | None = None

    def mock(self, *, return_value: Response) -> Route:
        self.return_value = return_value
        return self


class Router:
    def __init__(self) -> None:
        self._routes: list[Route] = []

    def post(self, url: str) -> Route:
        route = Route(url)
        self._routes.append(route)
        return route

    def dispatch(
        self,
        url: str,
        *,
        data: Any = None,
        json: Any = None,
        headers: Any = None,
    ) -> Response:
        path = str(url).split("?", 1)[0]
        match = next(
            (
                route
                for route in self._routes
                if route.url == path and route.return_value is not None
            ),
            None,
        )
        if match is None or match.return_value is None:
            raise AssertionError(f"No mock for POST {url}")
        if isinstance(data, dict):
            content = urlencode(data).encode()
        elif json is not None:
            content = json_dumps(json)
        elif data is None:
            content = b""
        elif isinstance(data, bytes):
            content = data
        else:
            content = str(data).encode()
        match.calls.add(_Request(content, dict(headers or {})))
        return match.return_value


def json_dumps(payload: Any) -> bytes:
    return json.dumps(payload).encode()


@contextmanager
def mock_transport() -> Generator[Router]:
    """Patch Session.post for a block that cannot take the mock_http fixture."""
    router = Router()
    original = Session.post

    def fake_post(
        self: Session,
        url: str,
        data: Any = None,
        json: Any = None,
        headers: Any = None,
        **kwargs: Any,
    ) -> Response:
        return router.dispatch(url, data=data, json=json, headers=headers)

    Session.post = fake_post
    try:
        yield router
    finally:
        Session.post = original
