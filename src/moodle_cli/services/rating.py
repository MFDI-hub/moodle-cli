"""Ratings."""

from __future__ import annotations

from typing import Any

from moodle_cli.services.base import BaseService


class RatingService(BaseService):
    def list_ratings(
        self,
        contextlevel: str,
        instanceid: int,
        component: str,
        ratingarea: str,
        itemid: int,
        scaleid: int,
    ) -> Any:
        return self.call(
            "core_rating_get_item_ratings",
            contextlevel=contextlevel,
            instanceid=instanceid,
            component=component,
            ratingarea=ratingarea,
            itemid=itemid,
            scaleid=scaleid,
        )

    def add(
        self,
        contextlevel: str,
        instanceid: int,
        component: str,
        ratingarea: str,
        itemid: int,
        scaleid: int,
        rating: int,
    ) -> Any:
        return self.call(
            "core_rating_add_rating",
            contextlevel=contextlevel,
            instanceid=instanceid,
            component=component,
            ratingarea=ratingarea,
            itemid=itemid,
            scaleid=scaleid,
            rating=rating,
        )
