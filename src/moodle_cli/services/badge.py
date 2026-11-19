"""Badges service — a user's awarded badges (read-only)."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from moodle_cli.services.base import BaseService, MoodleModel


class BadgeRecord(MoodleModel):
    id: int = 0
    name: str = ""
    description: str = ""
    course_id: Annotated[int | None, Field(validation_alias="courseid")] = None
    date_issued: Annotated[int, Field(validation_alias="dateissued")] = 0
    issuer_name: Annotated[str, Field(validation_alias="issuername")] = ""


class BadgeService(BaseService):
    def user_badges(self, user_id: int, course_id: int | None = None) -> list[BadgeRecord]:
        params: dict[str, object] = {"userid": user_id}
        if course_id is not None:
            params["courseid"] = course_id
        data = self.call("core_badges_get_user_badges", **params)
        return [BadgeRecord.model_validate(b) for b in data.get("badges", [])]
