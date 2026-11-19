"""Activities, sections, assignments, forums, and quizzes.

Dataclasses for course modules. Extra payloads (forum posts, quiz attempts, …) load lazily.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any

from moodle_cli.api.models.base import Remote
from moodle_cli.api.models.common import FileRef
from moodle_cli.exceptions import MoodleAPIError

if TYPE_CHECKING:
    from moodle_cli.api.moodle import Moodle

_INNER_READERS: dict[str, str] = {
    "workshop": "submissions",
    "glossary": "entries",
    "data": "entries",
    "database": "entries",
    "wiki": "pages",
    "lesson": "pages",
    "choice": "results",
    "feedback": "analysis",
}


@dataclass
class Activity(Remote):
    id: int
    name: str
    mod_name: str
    url: str = ""
    visible: int = 1
    instance: int = 0
    text: str = ""
    target: str = ""
    table: list[dict[str, Any]] = field(default_factory=list)
    files: list[FileRef] = field(default_factory=list)

    @classmethod
    def from_module(cls, api: Moodle, raw: dict[str, Any]) -> Activity:
        files = [
            FileRef(_api=api, name=str(item.get("name") or ""), url=str(item.get("url") or ""))
            for item in raw.get("files") or []
            if isinstance(item, dict)
        ]
        ident = int(raw.get("id") or 0)
        return cls(
            _api=api,
            id=ident,
            name=str(raw.get("name") or ""),
            mod_name=str(raw.get("modname") or ""),
            url=str(raw.get("url") or ""),
            visible=int(raw.get("visible") or 0),
            instance=int(raw.get("instance") or ident or 0),
            text=str(raw.get("text") or ""),
            target=str(raw.get("target") or ""),
            table=list(raw.get("table") or []),
            files=files,
        )

    @cached_property
    def extra(self) -> Any:
        """Inner payload for workshop, glossary, wiki, lesson, database, choice, feedback."""
        ident = self.instance or self.id
        if not ident or self.mod_name not in _INNER_READERS:
            return None
        from moodle_cli.services.activity_content import (
            DatabaseService,
            GlossaryService,
            LessonService,
            WikiService,
            WorkshopService,
        )
        from moodle_cli.services.choice import ChoiceService
        from moodle_cli.services.feedback import FeedbackService

        client = self._api.client
        if self.mod_name == "workshop":
            return WorkshopService(client).submissions(ident)
        if self.mod_name == "glossary":
            return GlossaryService(client).entries(ident)
        if self.mod_name in {"data", "database"}:
            return DatabaseService(client).entries(ident)
        if self.mod_name == "wiki":
            return WikiService(client).subwiki_pages(ident)
        if self.mod_name == "lesson":
            return LessonService(client).pages(ident)
        if self.mod_name == "choice":
            return ChoiceService(client).get_results(ident)
        if self.mod_name == "feedback":
            return FeedbackService(client).get_analysis(ident)
        return None

    def extra_or_error(self) -> Any:
        try:
            return self.extra
        except MoodleAPIError as exc:
            return {"error": str(exc)}


@dataclass
class Section(Remote):
    id: int
    name: str
    summary: str = ""
    table: list[dict[str, Any]] = field(default_factory=list)
    activities: list[Activity] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["modules"] = data.pop("activities")
        return data


@dataclass
class Assignment(Remote):
    id: int
    cmid: int
    course_id: int
    name: str
    due_date: int = 0

    @cached_property
    def status(self) -> dict[str, Any]:
        from moodle_cli.services.assign import AssignService

        return AssignService(self._api.client).get_submission_status(self.id)

    @cached_property
    def files(self) -> list[FileRef]:
        activity = self._api.course(self.course_id).activity(self.cmid)
        return list(activity.files) if activity else []

    @cached_property
    def submissions(self) -> list[dict[str, Any]]:
        from moodle_cli.services.assign import AssignService

        return [
            row.model_dump() for row in AssignService(self._api.client).get_submissions([self.id])
        ]


@dataclass
class Discussion(Remote):
    id: int
    forum_id: int
    subject: str
    author: str = ""
    replies: int = 0
    time_modified: int = 0
    last_author: str = ""

    @cached_property
    def posts(self) -> list[dict[str, Any]]:
        from moodle_cli.services.forum import ForumService

        rows: list[dict[str, Any]] = []
        for post in ForumService(self._api.client).get_posts(self.id):
            data = post.model_dump()
            data["author_name"] = post.author_name
            rows.append(data)
        return rows


@dataclass
class Forum(Remote):
    id: int
    course_id: int
    name: str
    intro: str = ""
    cmid: int = 0
    type: str = ""

    @cached_property
    def discussions(self) -> list[Discussion]:
        from moodle_cli.services.forum import ForumService

        rows = ForumService(self._api.client).get_discussions(self.id)
        return [
            Discussion(
                _api=self._api,
                id=int(row.discussion or row.id),
                forum_id=self.id,
                subject=row.subject or row.name,
                author=row.user_full_name,
                replies=row.num_replies,
                time_modified=row.time_modified,
                last_author=row.user_modified_full_name,
            )
            for row in rows
        ]


@dataclass
class Quiz(Remote):
    id: int
    course_id: int
    cmid: int
    name: str
    grade: float = 0

    @cached_property
    def attempts(self) -> list[dict[str, Any]]:
        from moodle_cli.services.quiz import QuizService

        return [row.model_dump() for row in QuizService(self._api.client).get_attempts(self.id)]
