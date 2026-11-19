"""Blog entries."""

from __future__ import annotations

from typing import Any

from moodle_cli.services.base import BaseService


class BlogService(BaseService):
    def entries(self, **filters: Any) -> list[dict[str, Any]]:
        data = self.call("core_blog_get_entries", **filters)
        entries: list[dict[str, Any]] = data.get("entries", []) if isinstance(data, dict) else data
        return entries

    def add(self, subject: str, summary: str) -> Any:
        return self.call(
            "core_blog_add_entry",
            subject=subject,
            summary=summary,
            summaryformat=1,
        )
