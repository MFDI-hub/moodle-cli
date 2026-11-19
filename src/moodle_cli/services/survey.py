"""Survey questions and answers."""

from __future__ import annotations

from typing import Any

from moodle_cli._utils import require_session
from moodle_cli.client.pages import class_inner, html_text
from moodle_cli.exceptions import MoodleAPIError
from moodle_cli.services.base import BaseService


class SurveyService(BaseService):
    def questions(self, survey_id: int, cmid: int = 0) -> Any:
        try:
            return self.call("mod_survey_get_questions", surveyid=survey_id)
        except MoodleAPIError:
            if cmid:
                return self._from_page(cmid)
            raise

    def responses(self, survey_id: int, cmid: int = 0) -> Any:
        try:
            return self.call("mod_survey_get_responses", surveyid=survey_id)
        except MoodleAPIError:
            if cmid:
                return self._from_page(cmid)
            raise

    def _from_page(self, cmid: int) -> dict[str, Any]:
        session = require_session(self.client)
        session._ensure()
        resp = session.session.get(f"{session.base_url}/mod/survey/view.php?id={cmid}")
        resp.raise_for_status()
        body = class_inner(resp.text, "generalbox") or class_inner(resp.text, "region-main")
        return {"html": body, "text": html_text(body or resp.text)}
