"""Course object: sections, people, grades, and dump.

:class:`Course` is the public course API. Web-service wrappers are imported inside methods
so this module does not import the service layer at load time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Any

from moodle_cli.api.models.activities import Activity, Assignment, Forum, Quiz, Section
from moodle_cli.api.models.base import Remote
from moodle_cli.api.models.common import (
    Badge,
    Choice,
    Completion,
    Event,
    Feedback,
    FileRef,
    Grade,
    Group,
    Note,
    User,
)
from moodle_cli.exceptions import MoodleAPIError


@dataclass
class Course(Remote):
    """A Moodle course with lazily loaded sections, people, grades, and files."""

    id: int
    short_name: str
    full_name: str
    category_id: int = 0
    visible: int = 1
    start_date: int = 0
    end_date: int = 0
    summary: str = ""
    format: str = "topics"
    last_access: int | None = None

    @cached_property
    def sections(self) -> list[Section]:
        from moodle_cli.services.course import CourseService

        raw = CourseService(self._api.client).get_contents(self.id)
        sections: list[Section] = []
        for item in raw:
            sections.append(
                Section(
                    _api=self._api,
                    id=item.id,
                    name=item.name,
                    summary=item.summary,
                    table=list(item.table),
                    activities=[Activity.from_module(self._api, mod) for mod in item.modules],
                )
            )
        return sections

    @property
    def contents(self) -> list[Section]:
        """Alias for ``sections`` — the full module outline plus page text and files."""
        return self.sections

    @property
    def activities(self) -> list[Activity]:
        return [activity for section in self.sections for activity in section.activities]

    def activity(self, cmid: int) -> Activity | None:
        return next((item for item in self.activities if item.id == cmid), None)

    def of(self, mod_name: str) -> list[Activity]:
        needle = mod_name.lower()
        return [item for item in self.activities if item.mod_name.lower() == needle]

    @property
    def files(self) -> list[FileRef]:
        found: list[FileRef] = []
        seen: set[str] = set()
        for activity in self.activities:
            for item in activity.files:
                if item.url and item.url not in seen:
                    seen.add(item.url)
                    found.append(item)
            if activity.target and activity.target not in seen:
                seen.add(activity.target)
                found.append(FileRef(_api=self._api, name=activity.name, url=activity.target))
            if activity.mod_name == "link" and activity.url and activity.url not in seen:
                seen.add(activity.url)
                found.append(FileRef(_api=self._api, name=activity.name, url=activity.url))
        return found

    @property
    def moodle_files(self) -> list[FileRef]:
        return [
            item for item in self.files if item.is_moodle and "/assignsubmission_" not in item.url
        ]

    @cached_property
    def assignments(self) -> list[Assignment]:
        from moodle_cli.services.assign import AssignService

        rows = AssignService(self._api.client).list_assignments([self.id])
        return [
            Assignment(
                _api=self._api,
                id=row.id,
                cmid=row.cmid,
                course_id=row.course,
                name=row.name,
                due_date=row.due_date,
            )
            for row in rows
        ]

    @cached_property
    def forums(self) -> list[Forum]:
        from moodle_cli.services.forum import ForumService

        rows = ForumService(self._api.client).list_forums(self.id)
        return [
            Forum(
                _api=self._api,
                id=row.id,
                course_id=self.id,
                name=row.name,
                intro=row.intro,
                type=row.type,
            )
            for row in rows
        ]

    @cached_property
    def quizzes(self) -> list[Quiz]:
        from moodle_cli.services.quiz import QuizService

        rows = QuizService(self._api.client).list_quizzes(self.id)
        return [
            Quiz(
                _api=self._api,
                id=row.id,
                course_id=self.id,
                cmid=row.course_module,
                name=row.name,
                grade=float(row.grade or 0),
            )
            for row in rows
        ]

    @cached_property
    def grades(self) -> list[Grade]:
        from moodle_cli.services.grade import GradeService

        return [
            Grade(
                _api=self._api,
                name=item.item_name or "",
                grade=item.grade or "",
                grade_max=item.grade_max,
                feedback=item.feedback,
            )
            for item in GradeService(self._api.client).get_grades(self.id)
        ]

    @cached_property
    def people(self) -> list[User]:
        from moodle_cli.services.enrol import EnrolService

        rows = EnrolService(self._api.client).list_enrolled_users(self.id)
        return [
            User(
                _api=self._api,
                id=row.id,
                username=row.username,
                full_name=row.full_name,
                first_name=row.first_name,
                last_name=row.last_name,
                email=row.email,
                last_access=row.last_access,
                last_course_access=row.last_course_access,
                roles=list(row.roles),
            )
            for row in rows
        ]

    @cached_property
    def groups(self) -> list[Group]:
        from moodle_cli.services.group import GroupService

        return [
            Group(
                _api=self._api,
                id=row.id,
                course_id=row.course_id or self.id,
                name=row.name,
                description=row.description,
            )
            for row in GroupService(self._api.client).list_groups(self.id)
        ]

    @cached_property
    def groupings(self) -> list[Group]:
        from moodle_cli.services.group import GroupService

        return [
            Group(
                _api=self._api,
                id=row.id,
                course_id=row.course_id or self.id,
                name=row.name,
                description=row.description,
            )
            for row in GroupService(self._api.client).list_groupings(self.id)
        ]

    @cached_property
    def calendar(self) -> list[Event]:
        from moodle_cli.services.calendar import CalendarService

        rows = CalendarService(self._api.client).get_course_events(self.id)
        return [
            Event(
                _api=self._api,
                id=row.id,
                name=row.name,
                course_id=row.course_id or self.id,
                event_type=row.event_type,
                time_start=row.time_start,
                description=row.description,
            )
            for row in rows
        ]

    @cached_property
    def completion(self) -> list[Completion]:
        from moodle_cli.services.completion import CompletionService

        return [
            Completion(
                _api=self._api,
                cmid=row.cmid,
                mod_name=row.mod_name,
                state=row.state,
                time_completed=row.time_completed,
                tracking=row.tracking,
            )
            for row in CompletionService(self._api.client).get_status(self.id)
        ]

    @cached_property
    def notes(self) -> list[Note]:
        from moodle_cli.services.note import NoteService

        return [
            Note(
                _api=self._api,
                id=int(row.get("id") or 0),
                course_id=int(row.get("courseid") or self.id),
                user_id=int(row.get("userid") or 0),
                content=str(row.get("content") or row.get("text") or ""),
            )
            for row in NoteService(self._api.client).course_notes(self.id)
        ]

    @cached_property
    def choices(self) -> list[Choice]:
        from moodle_cli.services.choice import ChoiceService

        return [
            Choice(
                _api=self._api,
                id=row.id,
                course_id=row.course or self.id,
                cmid=row.course_module,
                name=row.name,
                intro=row.intro,
            )
            for row in ChoiceService(self._api.client).list_choices(self.id)
        ]

    @cached_property
    def feedbacks(self) -> list[Feedback]:
        from moodle_cli.services.feedback import FeedbackService

        return [
            Feedback(
                _api=self._api,
                id=row.id,
                course_id=row.course or self.id,
                cmid=row.course_module,
                name=row.name,
                intro=row.intro,
            )
            for row in FeedbackService(self._api.client).list_feedbacks(self.id)
        ]

    @cached_property
    def badges(self) -> list[Badge]:
        from moodle_cli.services.badge import BadgeService

        return [
            Badge(
                _api=self._api,
                id=row.id,
                name=row.name,
                description=row.description,
                course_id=int(row.course_id or self.id),
                date_issued=row.date_issued,
                issuer=row.issuer_name,
            )
            for row in BadgeService(self._api.client).user_badges(self._api.me.id, self.id)
        ]

    def _load_list(self, name: str) -> list[Any]:
        try:
            return list(getattr(self, name))
        except MoodleAPIError:
            return []

    def snapshot(self, *, deep: bool = False) -> dict[str, Any]:
        """Load the module into a plain dict. ``deep`` walks forums and activity extras."""
        sections: list[dict[str, Any]] = []
        for section in self.sections:
            row = section.to_dict()
            if deep:
                for activity, module in zip(section.activities, row["modules"], strict=True):
                    extra = activity.extra_or_error()
                    if extra is not None:
                        module["extra"] = extra
            sections.append(row)
        data: dict[str, Any] = {
            "id": self.id,
            "short_name": self.short_name,
            "full_name": self.full_name,
            "sections": sections,
            "assignments": [row.to_dict() for row in self._load_list("assignments")],
            "forums": [row.to_dict() for row in self._load_list("forums")],
            "quizzes": [row.to_dict() for row in self._load_list("quizzes")],
            "grades": [row.to_dict() for row in self._load_list("grades")],
            "people": [row.to_dict() for row in self._load_list("people")],
            "groups": [row.to_dict() for row in self._load_list("groups")],
            "groupings": [row.to_dict() for row in self._load_list("groupings")],
            "calendar": [row.to_dict() for row in self._load_list("calendar")],
            "completion": [row.to_dict() for row in self._load_list("completion")],
            "notes": [row.to_dict() for row in self._load_list("notes")],
            "choices": [row.to_dict() for row in self._load_list("choices")],
            "feedbacks": [row.to_dict() for row in self._load_list("feedbacks")],
            "badges": [row.to_dict() for row in self._load_list("badges")],
        }
        if deep:
            data["assignments"] = [
                {**row.to_dict(), "status": row.status} for row in self.assignments
            ]
            data["quizzes"] = [{**row.to_dict(), "attempts": row.attempts} for row in self.quizzes]
            data["forums"] = [
                {
                    **forum.to_dict(),
                    "discussions": [
                        {**disc.to_dict(), "posts": disc.posts} for disc in forum.discussions
                    ],
                }
                for forum in self.forums
            ]
            data["choices"] = [{**row.to_dict(), "results": row.results} for row in self.choices]
            data["feedbacks"] = [
                {**row.to_dict(), "analysis": row.analysis} for row in self.feedbacks
            ]
        return data

    def get_everything(self, *, deep: bool = True) -> dict[str, Any]:
        """All course objects as a dict. Default ``deep`` includes forum posts."""
        return self.snapshot(deep=deep)

    def export_pages(self, dest: str | Path, fmt: str = "md", *, deep: bool = False) -> Path:
        """Save page text, tables, and links as ``md``, ``html``, or ``txt``."""
        from moodle_cli.api.export import write_pages

        return write_pages(self, dest, fmt, deep=deep)

    def dump(
        self,
        dest: str | Path,
        *,
        files: bool = True,
        deep: bool = False,
        pages: str | None = "md",
    ) -> Path:
        """Write ``course.json``, optional page files, and Moodle attachments under ``dest``."""
        from moodle_cli.api.export import file_save_name, write_pages

        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        payload = self.snapshot(deep=deep)
        (dest / "course.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if pages and pages.lower() not in {"none", "off", "no"}:
            write_pages(self, dest, pages, deep=deep)
        if files:
            folder = dest / "files"
            folder.mkdir(exist_ok=True)
            used: set[str] = set()
            for item in self.moodle_files:
                name = file_save_name(item.name, item.url)
                target = folder / name
                stem, suffix = target.stem, target.suffix
                index = 1
                while str(target) in used:
                    index += 1
                    target = folder / f"{stem}_{index}{suffix}"
                used.add(str(target))
                if target.exists() and target.stat().st_size > 0:
                    continue
                item.download(target)
        return dest
