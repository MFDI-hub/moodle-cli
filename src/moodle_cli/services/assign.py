"""Assignment service."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from moodle_cli.services.base import BaseService, MoodleModel


class AssignmentRecord(MoodleModel):
    id: int
    cmid: int = 0
    course: int = 0
    name: str = ""
    due_date: Annotated[int, Field(validation_alias="duedate")] = 0
    grade: float = 0


class Submission(MoodleModel):
    id: int
    user_id: Annotated[int, Field(validation_alias="userid")] = 0
    status: str = ""
    time_modified: Annotated[int, Field(validation_alias="timemodified")] = 0
    grading_status: Annotated[str, Field(validation_alias="gradingstatus")] = ""


class AssignService(BaseService):
    def list_assignments(self, course_ids: list[int] | None = None) -> list[AssignmentRecord]:
        params: dict[str, Any] = {}
        if course_ids:
            params["courseids"] = course_ids
        data = self.call("mod_assign_get_assignments", **params)
        assignments = []
        for course_data in data.get("courses", []):
            for a in course_data.get("assignments", []):
                assignments.append(AssignmentRecord.model_validate(a))
        return assignments

    def get_submissions(self, assignment_ids: list[int]) -> list[Submission]:
        data = self.call("mod_assign_get_submissions", assignmentids=assignment_ids)
        submissions = []
        for a in data.get("assignments", []):
            for s in a.get("submissions", []):
                submissions.append(Submission.model_validate(s))
        return submissions

    def get_grades(self, assignment_ids: list[int]) -> list[dict[str, Any]]:
        """Grades already given on assignments (mod_assign_get_grades)."""
        data = self.call("mod_assign_get_grades", assignmentids=assignment_ids)
        grades: list[dict[str, Any]] = []
        for a in data.get("assignments", []):
            for g in a.get("grades", []):
                grades.append({"assignment": a.get("assignmentid"), **g})
        return grades

    def submission_files(self, assignment_id: int) -> list[dict[str, Any]]:
        """File URLs attached to submissions (including student uploads)."""
        data = self.call("mod_assign_get_submissions", assignmentids=[assignment_id])
        files: list[dict[str, Any]] = []
        for assignment in data.get("assignments", []):
            for submission in assignment.get("submissions", []):
                for plugin in submission.get("plugins") or []:
                    for area in plugin.get("fileareas") or []:
                        for item in area.get("files") or []:
                            url = str(item.get("fileurl") or item.get("url") or "")
                            if not url:
                                continue
                            files.append(
                                {
                                    "url": url,
                                    "name": str(item.get("filename") or item.get("name") or "file"),
                                    "size": int(item.get("filesize") or item.get("size") or 0),
                                    "timemodified": int(item.get("timemodified") or 0),
                                }
                            )
        return files

    def save_submission(self, assignment_id: int, plugin_data: dict[str, Any]) -> Any:
        return self.call(
            "mod_assign_save_submission",
            assignmentid=assignment_id,
            plugindata=plugin_data,
        )

    def submit_for_grading(self, assignment_id: int, accept_statement: int = 1) -> Any:
        return self.call(
            "mod_assign_submit_for_grading",
            assignmentid=assignment_id,
            acceptsubmissionstatement=accept_statement,
        )

    def get_submission_status(self, assign_id: int, user_id: int | None = None) -> dict[str, Any]:
        """Per-user submission + grading status (mod_assign_get_submission_status)."""
        params: dict[str, Any] = {"assignid": assign_id}
        if user_id is not None:
            params["userid"] = user_id
        status: dict[str, Any] = self.call("mod_assign_get_submission_status", **params)
        return status

    def grade_submission(
        self,
        assignment_id: int,
        user_id: int,
        grade: float,
        feedback: str = "",
        workflow_state: str = "",
        advanced_grading: dict[str, Any] | None = None,
    ) -> None:
        # `workflowstate` MUST stay empty unless the assignment has marking
        # workflow enabled (markingworkflow=1). Sending a non-empty state such as
        # "graded" to an assignment with marking workflow OFF makes Moodle reject
        # the whole call with "Invalid parameter value detected" — so the grade
        # never lands. Default to "" (valid for both workflow-on and workflow-off);
        # callers grading a workflow-enabled assignment can pass an explicit state
        # (e.g. "released") via the CLI's --workflow-state.
        self.call(
            "mod_assign_save_grade",
            assignmentid=assignment_id,
            userid=user_id,
            grade=grade,
            attemptnumber=-1,
            addattempt=0,
            workflowstate=workflow_state,
            # `applytoall` is required by mod_assign_save_grade — omitting it is
            # rejected as "Invalid parameter value detected". 0 = grade only this
            # user (correct for a per-user grade; on a team-submission assignment 1
            # would blanket the whole team, which this command must not do).
            applytoall=0,
            plugindata={"assignfeedbackcomments_editor": {"text": feedback, "format": 1}},
            **({"advancedgradingdata": advanced_grading} if advanced_grading else {}),
        )

    def grading_definitions(self, cmid: int) -> Any:
        return self.call(
            "core_grading_get_definitions",
            cmids=[cmid],
            arenaname="mod_assign",
            activeonly=1,
        )
