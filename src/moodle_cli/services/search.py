"""Global site search."""

from __future__ import annotations

from typing import Any

from moodle_cli.exceptions import MoodleAPIError
from moodle_cli.services.base import BaseService


class SearchService(BaseService):
    def results(self, query: str, page: int = 0) -> dict[str, Any]:
        try:
            data: dict[str, Any] = self.call("core_search_get_results", query=query, page=page)
        except MoodleAPIError as exc:
            if exc.error_code in {"servicenotavailable", "nopermissions"}:
                raise MoodleAPIError(
                    "Global search is not enabled on this site.",
                    error_code=exc.error_code,
                    debug_info=exc.debug_info,
                ) from exc
            raise
        return data
