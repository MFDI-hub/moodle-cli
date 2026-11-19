"""Groups service — course groups, groupings, and a user's group memberships."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from moodle_cli.services.base import BaseService, MoodleModel


class GroupRecord(MoodleModel):
    id: int
    course_id: Annotated[int, Field(validation_alias="courseid")] = 0
    name: str = ""
    description: str = ""
    description_format: Annotated[int, Field(validation_alias="descriptionformat")] = 1


class Grouping(MoodleModel):
    id: int
    course_id: Annotated[int, Field(validation_alias="courseid")] = 0
    name: str = ""
    description: str = ""


class GroupService(BaseService):
    def list_groups(self, course_id: int) -> list[GroupRecord]:
        data = self.call("core_group_get_course_groups", courseid=course_id)
        return [GroupRecord.model_validate(g) for g in data]

    def list_groupings(self, course_id: int) -> list[Grouping]:
        data = self.call("core_group_get_course_groupings", courseid=course_id)
        return [Grouping.model_validate(g) for g in data]

    def user_groups(self, course_id: int, user_id: int) -> list[GroupRecord]:
        data = self.call(
            "core_group_get_course_user_groups",
            courseid=course_id,
            userid=user_id,
        )
        return [GroupRecord.model_validate(g) for g in data.get("groups", [])]

    def create_groups(self, course_id: int, name: str, description: str = "") -> list[GroupRecord]:
        data = self.call(
            "core_group_create_groups",
            groups=[{"courseid": course_id, "name": name, "description": description}],
        )
        return [GroupRecord.model_validate(g) for g in data]

    def delete_groups(self, group_ids: list[int]) -> None:
        self.call("core_group_delete_groups", groupids=group_ids)

    def add_members(self, group_id: int, user_ids: list[int]) -> None:
        self.call(
            "core_group_add_group_members",
            members=[{"groupid": group_id, "userid": uid} for uid in user_ids],
        )

    def remove_members(self, group_id: int, user_ids: list[int]) -> None:
        self.call(
            "core_group_delete_group_members",
            members=[{"groupid": group_id, "userid": uid} for uid in user_ids],
        )

    def create_grouping(self, course_id: int, name: str, description: str = "") -> Any:
        return self.call(
            "core_group_create_groupings",
            groupings=[{"courseid": course_id, "name": name, "description": description}],
        )

    def assign_grouping(self, grouping_id: int, group_ids: list[int]) -> None:
        self.call(
            "core_group_assign_grouping",
            groupingid=grouping_id,
            assignments=[{"groupid": gid} for gid in group_ids],
        )
