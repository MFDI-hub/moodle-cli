"""User service."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from moodle_cli.services.base import BaseService, MoodleModel


class UserRecord(MoodleModel):
    id: int
    username: str = ""
    full_name: Annotated[str, Field(validation_alias="fullname")] = ""
    first_name: Annotated[str, Field(validation_alias="firstname")] = ""
    last_name: Annotated[str, Field(validation_alias="lastname")] = ""
    email: str = ""
    department: str = ""
    institution: str = ""
    profile_image_url: Annotated[str, Field(validation_alias="profileimageurl")] = ""


class UserService(BaseService):
    def get_me(self) -> UserRecord:
        data = self.call("core_webservice_get_site_info")
        return UserRecord.model_validate(
            {
                "id": data["userid"],
                "username": data["username"],
                "fullname": data["fullname"],
                "firstname": data.get("firstname", ""),
                "lastname": data.get("lastname", ""),
            }
        )

    def list_users(self, key: str = "email", value: str = "") -> list[UserRecord]:
        data = self.call(
            "core_user_get_users",
            criteria=[{"key": key, "value": value}],
        )
        return [UserRecord.model_validate(u) for u in data.get("users", [])]

    def get_user(self, user_id: int) -> UserRecord:
        data = self.call(
            "core_user_get_users_by_field",
            field="id",
            values=[str(user_id)],
        )
        return UserRecord.model_validate(data[0])

    def course_profiles(self, course_id: int, user_ids: list[int]) -> list[UserRecord]:
        """Per-course user profiles (core_user_get_course_user_profiles)."""
        data = self.call(
            "core_user_get_course_user_profiles",
            userlist=[{"userid": uid, "courseid": course_id} for uid in user_ids],
        )
        return [UserRecord.model_validate(u) for u in data]

    def create_user(
        self,
        username: str,
        first_name: str,
        last_name: str,
        email: str,
        password: str,
        **kwargs: Any,
    ) -> UserRecord:
        user_data = {
            "username": username,
            "firstname": first_name,
            "lastname": last_name,
            "email": email,
            "password": password,
            **kwargs,
        }
        data = self.call("core_user_create_users", users=[user_data])
        return UserRecord.model_validate(data[0])

    def update_user(
        self, user_id: int, custom_fields: list[dict[str, Any]] | None = None, **kwargs: Any
    ) -> None:
        user_data: dict[str, Any] = {"id": user_id, **kwargs}
        if custom_fields:
            user_data["customfields"] = custom_fields
        self.call("core_user_update_users", users=[user_data])

    def delete_users(self, user_ids: list[int]) -> None:
        self.call("core_user_delete_users", userids=user_ids)
