"""Quiz service."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from moodle_cli.services.base import BaseService, MoodleModel


class QuizRecord(MoodleModel):
    id: int
    course: int = 0
    course_module: Annotated[int, Field(validation_alias="coursemodule")] = 0
    name: str = ""
    time_open: Annotated[int, Field(validation_alias="timeopen")] = 0
    time_close: Annotated[int, Field(validation_alias="timeclose")] = 0
    grade: float = 0


class QuizAttempt(MoodleModel):
    id: int
    quiz: int = 0
    user_id: Annotated[int, Field(validation_alias="userid")] = 0
    attempt: int = 0
    state: str = ""
    grade: float | None = None
    time_start: Annotated[int, Field(validation_alias="timestart")] = 0
    time_finish: Annotated[int, Field(validation_alias="timefinish")] = 0


class QuizService(BaseService):
    def list_quizzes(self, course_id: int) -> list[QuizRecord]:
        data = self.call("mod_quiz_get_quizzes_by_courses", courseids=[course_id])
        return [QuizRecord.model_validate(q) for q in data.get("quizzes", [])]

    def get_attempts(self, quiz_id: int, user_id: int | None = None) -> list[QuizAttempt]:
        params = {"quizid": quiz_id, "status": "all"}
        if user_id is not None:
            params["userid"] = user_id
        data = self.call("mod_quiz_get_user_attempts", **params)
        return [QuizAttempt.model_validate(a) for a in data.get("attempts", [])]

    def best_grade(self, quiz_id: int, user_id: int | None = None) -> dict[str, object]:
        """A user's best grade on a quiz (mod_quiz_get_user_best_grade)."""
        params: dict[str, object] = {"quizid": quiz_id}
        if user_id is not None:
            params["userid"] = user_id
        result: dict[str, object] = self.call("mod_quiz_get_user_best_grade", **params)
        return result

    def start_attempt(self, quiz_id: int) -> dict[str, Any]:
        data: dict[str, Any] = self.call("mod_quiz_start_attempt", quizid=quiz_id)
        return data

    def attempt_data(self, attempt_id: int, page: int = 0) -> dict[str, Any]:
        data: dict[str, Any] = self.call(
            "mod_quiz_get_attempt_data", attemptid=attempt_id, page=page
        )
        return data

    def save_attempt(self, attempt_id: int, answers: dict[str, Any]) -> Any:
        data = [{"name": key, "value": value} for key, value in answers.items()]
        return self.call("mod_quiz_save_attempt", attemptid=attempt_id, data=data)

    def process_attempt(
        self, attempt_id: int, answers: dict[str, Any] | None = None, finish: bool = False
    ) -> Any:
        data = [{"name": key, "value": value} for key, value in (answers or {}).items()]
        return self.call(
            "mod_quiz_process_attempt",
            attemptid=attempt_id,
            data=data,
            finishattempt=int(finish),
        )

    def attempt_review(self, attempt_id: int) -> dict[str, Any]:
        """Full review of a finished attempt — questions, responses, marks, feedback
        (mod_quiz_get_attempt_review)."""
        review: dict[str, Any] = self.call("mod_quiz_get_attempt_review", attemptid=attempt_id)
        return review
