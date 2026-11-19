"""Grade service."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from moodle_cli.services.base import BaseService, MoodleModel


class GradeItem(MoodleModel):
    item_name: Annotated[str | None, Field(validation_alias="itemname")] = None
    grade: str | None = None
    grade_max: Annotated[float, Field(validation_alias="grademax")] = 0
    grade_min: Annotated[float, Field(validation_alias="grademin")] = 0
    feedback: str = ""


class GradeReport(MoodleModel):
    user_grades: Annotated[list[dict[str, Any]], Field(validation_alias="usergrades")] = []


class GradeService(BaseService):
    def get_grades(self, course_id: int, user_id: int | None = None) -> list[GradeItem]:
        params: dict[str, Any] = {"courseid": course_id}
        if user_id is not None:
            params["userid"] = user_id
        data = self.call("gradereport_user_get_grade_items", **params)
        items = []
        for ug in data.get("usergrades", []):
            for gi in ug.get("gradeitems", []):
                items.append(GradeItem.model_validate(gi))
        return items

    def get_report(self, course_id: int, user_id: int | None = None) -> GradeReport:
        params: dict[str, Any] = {"courseid": course_id}
        if user_id is not None:
            params["userid"] = user_id
        data = self.call("gradereport_user_get_grade_items", **params)
        return GradeReport.model_validate(data)

    def get_overview(self) -> list[dict[str, Any]]:
        """Current user's final grade in each of their courses.

        gradereport_overview_get_course_grades — the one-number-per-course view.
        """
        data = self.call("gradereport_overview_get_course_grades")
        grades: list[dict[str, Any]] = data.get("grades", [])
        return grades

    def get_grades_table(self, course_id: int, user_id: int | None = None) -> dict[str, Any]:
        """Full grader-style table for a course (gradereport_user_get_grades_table)."""
        params: dict[str, Any] = {"courseid": course_id}
        if user_id is not None:
            params["userid"] = user_id
        table: dict[str, Any] = self.call("gradereport_user_get_grades_table", **params)
        return table
