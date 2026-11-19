"""Tags."""

from __future__ import annotations

from typing import Any

from moodle_cli.services.base import BaseService


class TagService(BaseService):
    def list_tags(self, query: str = "") -> list[dict[str, Any]]:
        if query:
            data = self.call("core_tag_get_tagindex", tagindex={"tag": query})
        else:
            data = self.call("core_tag_get_tag_cloud")
        if isinstance(data, dict):
            tags = data.get("tags") or data.get("items") or data.get("tagcloud") or []
            if isinstance(tags, dict):
                tags = tags.get("tags") or []
            return list(tags)
        return list(data)
