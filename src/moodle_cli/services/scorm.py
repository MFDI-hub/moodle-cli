"""SCORM SCOs and tracks."""

from __future__ import annotations

from typing import Any

from moodle_cli.services.base import BaseService


class ScormService(BaseService):
    def scoes(self, scorm_id: int) -> Any:
        return self.call("mod_scorm_get_scorm_scoes", scormid=scorm_id)

    def tracks(self, sco_id: int, user_id: int, attempt: int = 1) -> Any:
        return self.call(
            "mod_scorm_get_scorm_sco_tracks",
            scoid=sco_id,
            userid=user_id,
            attempt=attempt,
        )

    def attempt_count(self, scorm_id: int, user_id: int) -> Any:
        return self.call(
            "mod_scorm_get_scorm_attempt_count",
            scormid=scorm_id,
            userid=user_id,
        )
