"""Comments on Moodle items."""

from __future__ import annotations

from typing import Any

from moodle_cli.services.base import BaseService


class CommentService(BaseService):
    def list_comments(
        self,
        contextlevel: str,
        instanceid: int,
        component: str,
        itemid: int,
        area: str = "",
    ) -> list[dict[str, Any]]:
        data = self.call(
            "core_comment_get_comments",
            contextlevel=contextlevel,
            instanceid=instanceid,
            component=component,
            itemid=itemid,
            area=area,
        )
        comments: list[dict[str, Any]] = (
            data.get("comments", []) if isinstance(data, dict) else data
        )
        return comments

    def add(
        self,
        contextlevel: str,
        instanceid: int,
        component: str,
        itemid: int,
        content: str,
        area: str = "",
    ) -> Any:
        return self.call(
            "core_comment_add_comments",
            comments=[
                {
                    "contextlevel": contextlevel,
                    "instanceid": instanceid,
                    "component": component,
                    "itemid": itemid,
                    "content": content,
                    "area": area,
                }
            ],
        )
