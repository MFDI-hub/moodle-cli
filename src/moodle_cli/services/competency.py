"""Competencies and learning plans."""

from __future__ import annotations

from typing import Any

from moodle_cli.services.base import BaseService


class CompetencyService(BaseService):
    def course_competencies(self, course_id: int) -> Any:
        return self.call("core_competency_list_course_competencies", courseid=course_id)

    def grade(
        self,
        course_id: int,
        competency_id: int,
        user_id: int,
        grade: int,
        note: str = "",
    ) -> Any:
        return self.call(
            "core_competency_grade_competency_in_course",
            courseid=course_id,
            competencyid=competency_id,
            userid=user_id,
            grade=grade,
            note=note,
        )
