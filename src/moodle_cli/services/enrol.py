"""Enrolment service."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from moodle_cli.exceptions import MoodleAPIError
from moodle_cli.services.base import BaseService, MoodleModel


class EnrolledCourse(MoodleModel):
    id: int
    short_name: Annotated[str, Field(validation_alias="shortname")]
    full_name: Annotated[str, Field(validation_alias="fullname")]
    enrolled_user_count: Annotated[int, Field(validation_alias="enrolledusercount")] = 0
    visible: int = 1
    # Engagement / recency signals returned by core_enrol_get_users_courses.
    # Moodle sends null (not 0) for "never accessed", so these must be nullable.
    last_access: Annotated[int | None, Field(validation_alias="lastaccess")] = None
    progress: float | None = None
    completed: bool | None = None


class EnrolledUser(MoodleModel):
    id: int
    username: str = ""
    full_name: Annotated[str, Field(validation_alias="fullname")] = ""
    first_name: Annotated[str, Field(validation_alias="firstname")] = ""
    last_name: Annotated[str, Field(validation_alias="lastname")] = ""
    email: str = ""
    roles: list[dict[str, Any]] = []
    # Activity signals returned by core_enrol_get_enrolled_users — previously
    # dropped by this model, which hid every engagement stat from the CLI.
    # Nullable: Moodle sends null for a user who has never accessed the course.
    last_access: Annotated[int | None, Field(validation_alias="lastaccess")] = None
    last_course_access: Annotated[int | None, Field(validation_alias="lastcourseaccess")] = None
    groups: list[dict[str, Any]] = []

    @property
    def role_names(self) -> str:
        return ", ".join(r.get("shortname", "") for r in self.roles) or "-"


class EnrolMethod(MoodleModel):
    id: int = 0
    course_id: Annotated[int, Field(validation_alias="courseid")] = 0
    type: str = ""
    name: str = ""
    status: str = ""


class EnrolService(BaseService):
    def get_my_courses(self, user_id: int | None = None) -> list[EnrolledCourse]:
        params = {}
        if user_id is not None:
            params["userid"] = user_id
        data = self.call("core_enrol_get_users_courses", **params)
        return [EnrolledCourse.model_validate(c) for c in data]

    def list_enrolled_users(self, course_id: int) -> list[EnrolledUser]:
        data = self.call("core_enrol_get_enrolled_users", courseid=course_id)
        return [EnrolledUser.model_validate(u) for u in data]

    def get_enrolment_methods(self, course_id: int) -> list[EnrolMethod]:
        data = self.call("core_enrol_get_course_enrolment_methods", courseid=course_id)
        return [EnrolMethod.model_validate(m) for m in data]

    def enrol_users(
        self,
        course_id: int,
        user_ids: list[int],
        role_id: int = 5,
    ) -> Any:
        enrolments = [{"roleid": role_id, "userid": uid, "courseid": course_id} for uid in user_ids]
        return self.call("enrol_manual_enrol_users", enrolments=enrolments)

    def unenrol_users(self, course_id: int, user_ids: list[int]) -> Any:
        enrolments = [{"userid": uid, "courseid": course_id} for uid in user_ids]
        return self.call("enrol_manual_unenrol_users", enrolments=enrolments)

    def self_enrol(self, course_id: int, password: str = "") -> Any:
        params: dict[str, Any] = {"courseid": course_id}
        if password:
            params["password"] = password
        return self.call("enrol_self_enrol_user", **params)

    def cohort_enrol(self, course_id: int, cohort_id: int) -> Any:
        try:
            return self.call(
                "enrol_cohort_add_instance",
                courseid=course_id,
                cohortid=cohort_id,
            )
        except MoodleAPIError as exc:
            raise MoodleAPIError(
                "Cohort enrolment is not exposed on this site's web service.",
                error_code=exc.error_code or "servicenotavailable",
                debug_info=exc.debug_info,
            ) from exc
