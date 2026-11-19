"""Site, people, files, and other small Moodle objects.

These dataclasses are the public object API. Nested web-service calls run on first access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Any

from moodle_cli.api.models.base import Remote


@dataclass
class Site(Remote):
    """Signed-in site metadata from ``core_webservice_get_site_info``."""

    name: str
    url: str
    username: str
    full_name: str
    user_id: int
    lang: str = ""
    release: str = ""
    version: str = ""
    functions: list[str] = field(default_factory=list)


@dataclass
class User(Remote):
    """A Moodle user record as exposed by the object API."""

    id: int
    username: str = ""
    full_name: str = ""
    first_name: str = ""
    last_name: str = ""
    email: str = ""
    last_access: int | None = None
    last_course_access: int | None = None
    roles: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class FileRef(Remote):
    """A named URL, usually a ``pluginfile.php`` attachment."""

    name: str
    url: str

    @property
    def is_moodle(self) -> bool:
        return "/pluginfile.php/" in self.url

    def download(self, dest: str | Path | None = None) -> Path:
        """Save this file. SharePoint and other external URLs are left as links."""
        from moodle_cli.services.file import FileService

        result = FileService(self._api.client).download(
            self.url, None if dest is None else str(dest)
        )
        return Path(result["path"])


@dataclass
class Category(Remote):
    id: int
    name: str
    parent: int = 0
    course_count: int = 0
    visible: int = 1


@dataclass
class Badge(Remote):
    id: int
    name: str
    description: str = ""
    course_id: int = 0
    date_issued: int = 0
    issuer: str = ""


@dataclass
class Message(Remote):
    id: int
    from_id: int = 0
    to_id: int = 0
    text: str = ""
    time_created: int = 0


@dataclass
class Conversation(Remote):
    id: int
    name: str = ""
    unread: int = 0
    member_count: int = 0

    @cached_property
    def messages(self) -> list[dict[str, Any]]:
        from moodle_cli.services.message import MessageService

        return MessageService(self._api.client).get_conversation_messages(self._api.me.id, self.id)


@dataclass
class Cohort(Remote):
    id: int
    name: str
    id_number: str = ""
    description: str = ""
    visible: bool = True


@dataclass
class Group(Remote):
    id: int
    course_id: int = 0
    name: str = ""
    description: str = ""


@dataclass
class Grade(Remote):
    name: str
    grade: str = ""
    grade_max: float = 0
    feedback: str = ""


@dataclass
class Note(Remote):
    id: int = 0
    course_id: int = 0
    user_id: int = 0
    content: str = ""


@dataclass
class Completion(Remote):
    cmid: int
    mod_name: str
    state: int = 0
    time_completed: int = 0
    tracking: int = 0


@dataclass
class Event(Remote):
    id: int
    name: str
    course_id: int = 0
    event_type: str = ""
    time_start: int = 0
    description: str = ""


@dataclass
class Choice(Remote):
    id: int
    course_id: int
    cmid: int
    name: str
    intro: str = ""

    @cached_property
    def results(self) -> list[dict[str, Any]]:
        from moodle_cli.services.choice import ChoiceService

        return ChoiceService(self._api.client).get_results(self.id)


@dataclass
class Feedback(Remote):
    id: int
    course_id: int
    cmid: int
    name: str
    intro: str = ""

    @cached_property
    def analysis(self) -> dict[str, Any]:
        from moodle_cli.services.feedback import FeedbackService

        return FeedbackService(self._api.client).get_analysis(self.id)
