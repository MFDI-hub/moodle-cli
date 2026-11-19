"""Choice module service — read-only views of choice activities and their results."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from moodle_cli.services.base import BaseService, MoodleModel


class ChoiceRecord(MoodleModel):
    id: int
    course: int = 0
    course_module: Annotated[int, Field(validation_alias="coursemodule")] = 0
    name: str = ""
    intro: str = ""


class ChoiceService(BaseService):
    def list_choices(self, course_id: int) -> list[ChoiceRecord]:
        data = self.call("mod_choice_get_choices_by_courses", courseids=[course_id])
        return [ChoiceRecord.model_validate(c) for c in data.get("choices", [])]

    def get_results(self, choice_id: int) -> list[dict[str, Any]]:
        data = self.call("mod_choice_get_choice_results", choiceid=choice_id)
        options: list[dict[str, Any]] = data.get("options", [])
        return options

    def submit(self, choice_id: int, responses: list[int]) -> Any:
        return self.call(
            "mod_choice_submit_choice_response",
            choiceid=choice_id,
            responses=responses,
        )
