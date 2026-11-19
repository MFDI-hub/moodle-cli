"""H5P activity attempts and results."""

from __future__ import annotations

from typing import Any

from moodle_cli.services.base import BaseService


class H5PService(BaseService):
    def attempts(self, h5pactivity_id: int, user_id: int | None = None) -> Any:
        params: dict[str, Any] = {"h5pactivityid": h5pactivity_id}
        if user_id is not None:
            params["userid"] = user_id
        return self.call("mod_h5pactivity_get_attempts", **params)

    def results(self, h5pactivity_id: int, attempt_id: int | None = None) -> Any:
        params: dict[str, Any] = {"h5pactivityid": h5pactivity_id}
        if attempt_id is not None:
            params["attemptid"] = attempt_id
        return self.call("mod_h5pactivity_get_results", **params)
