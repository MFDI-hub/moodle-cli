"""Feedback (survey) module service — read-only views of feedback activities."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from moodle_cli.services.base import BaseService, MoodleModel


class FeedbackRecord(MoodleModel):
    id: int
    course: int = 0
    course_module: Annotated[int, Field(validation_alias="coursemodule")] = 0
    name: str = ""
    intro: str = ""
    anonymous: int = 0


class FeedbackService(BaseService):
    def list_feedbacks(self, course_id: int) -> list[FeedbackRecord]:
        data = self.call("mod_feedback_get_feedbacks_by_courses", courseids=[course_id])
        return [FeedbackRecord.model_validate(f) for f in data.get("feedbacks", [])]

    def get_analysis(self, feedback_id: int) -> dict[str, Any]:
        """Aggregated, anonymised analysis of responses (mod_feedback_get_analysis)."""
        analysis: dict[str, Any] = self.call("mod_feedback_get_analysis", feedbackid=feedback_id)
        return analysis

    def non_respondents(self, feedback_id: int) -> list[dict[str, Any]]:
        data = self.call("mod_feedback_get_non_respondents", feedbackid=feedback_id)
        users: list[dict[str, Any]] = data.get("users", [])
        return users

    def page_items(self, feedback_id: int, page: int = 0) -> dict[str, Any]:
        data: dict[str, Any] = self.call(
            "mod_feedback_get_page_items", feedbackid=feedback_id, page=page
        )
        return data

    def process_page(self, feedback_id: int, page: int, answers: dict[str, Any]) -> Any:
        return self.call(
            "mod_feedback_process_page",
            feedbackid=feedback_id,
            page=page,
            responses=answers,
        )
