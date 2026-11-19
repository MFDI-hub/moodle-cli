"""High-level Moodle session: load a profile, then ask for objects."""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from functools import cached_property
from pathlib import Path
from typing import Any, overload

from moodle_cli.api.models import (
    Badge,
    Category,
    Cohort,
    Conversation,
    Course,
    Event,
    FileRef,
    Message,
    Site,
    User,
    safe_name,
)
from moodle_cli.client.http import MoodleHTTPClient
from moodle_cli.client.session import MoodleSessionClient
from moodle_cli.client.storage import site_url_from_storage
from moodle_cli.config.auth import TokenStore
from moodle_cli.config.manager import ConfigManager
from moodle_cli.exceptions import AuthenticationError, MoodleAPIError, ProfileNotFoundError
from moodle_cli.services.badge import BadgeService
from moodle_cli.services.calendar import CalendarService
from moodle_cli.services.cohort import CohortService
from moodle_cli.services.course import CourseRecord, CourseService
from moodle_cli.services.enrol import EnrolService
from moodle_cli.services.file import FileService
from moodle_cli.services.message import MessageService
from moodle_cli.services.site import SiteService
from moodle_cli.services.user import UserService


class CourseCollection(Sequence[Course]):
    """Lazy list of the signed-in user's courses. Index by id, short name, or position."""

    def __init__(self, api: Moodle, loader: Any) -> None:
        self._api = api
        self._loader = loader
        self._items: list[Course] | None = None

    def _all(self) -> list[Course]:
        if self._items is None:
            self._items = [self._api._course_from(record) for record in self._loader()]
        return self._items

    def __iter__(self) -> Iterator[Course]:
        return iter(self._all())

    def __len__(self) -> int:
        return len(self._all())

    @overload
    def __getitem__(self, index: int) -> Course: ...

    @overload
    def __getitem__(self, index: slice) -> list[Course]: ...

    @overload
    def __getitem__(self, index: str) -> Course: ...

    def __getitem__(self, index: int | slice | str) -> Course | list[Course]:
        if isinstance(index, str):
            return self.by_short_name(index)
        return self._all()[index]

    def by_id(self, course_id: int) -> Course:
        for course in self._all():
            if course.id == course_id:
                return course
        return self._api.course(course_id)

    def by_short_name(self, short_name: str) -> Course:
        needle = short_name.lower()
        courses = self._all()
        for course in courses:
            if course.short_name.lower() == needle:
                return course
        hits = [course for course in courses if course.short_name.lower().startswith(f"{needle}-")]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            names = ", ".join(course.short_name for course in hits)
            raise MoodleAPIError(
                f"Ambiguous course short name {short_name}: {names}",
                error_code="invalidrecord",
            )
        raise MoodleAPIError(
            f"Course not in this session: {short_name}", error_code="invalidrecord"
        )


class Moodle:
    """One signed-in Moodle site. Objects behind properties are fetched on first use.

    >>> moodle = Moodle.load("soton")
    >>> course = moodle.course("COMP3204")
    >>> course.sections[2].activities
    >>> course.dump("COMP3204")
    >>> moodle.dump("moodle-dump")
    """

    def __init__(self, client: MoodleHTTPClient) -> None:
        self.client = client

    @classmethod
    def connect(
        cls,
        profile: str | None = None,
        storage_state: str | Path | None = None,
        url: str | None = None,
        *,
        readonly: bool = True,
    ) -> Moodle:
        """Build a session from a CLI profile and/or a Playwright storage-state file."""
        if storage_state:
            site = url
            if site is None:
                try:
                    _, prof = ConfigManager().get_profile(profile)
                    site = prof.url
                except ProfileNotFoundError:
                    site = None
            return cls.session(storage_state, site, readonly=readonly)
        return cls.load(profile, readonly=readonly)

    @classmethod
    def load(cls, profile: str | None = None, *, readonly: bool = True) -> Moodle:
        """Use a saved CLI profile (browser session or token)."""
        name, prof = ConfigManager().get_profile(profile)
        if prof.storage_state:
            return cls.session(prof.storage_state, prof.url, readonly=readonly)
        token = TokenStore().get(name)
        if not token:
            raise AuthenticationError(f"No token for profile '{name}'. Run: moodle auth login")
        return cls(
            MoodleHTTPClient(
                base_url=prof.url,
                token=token,
                service=prof.service,
                readonly=readonly,
            )
        )

    @classmethod
    def session(
        cls,
        storage_state: str | Path,
        url: str | None = None,
        *,
        readonly: bool = True,
    ) -> Moodle:
        """Use a Playwright storage-state file."""
        path = Path(storage_state)
        return cls(
            MoodleSessionClient(
                url or site_url_from_storage(path),
                path,
                readonly=readonly,
            )
        )

    @cached_property
    def site(self) -> Site:
        info = SiteService(self.client).get_site_info()
        return Site(
            _api=self,
            name=info.site_name,
            url=info.site_url,
            username=info.username,
            full_name=info.full_name,
            user_id=info.user_id,
            lang=info.lang,
            release=info.release,
            version=info.version,
            functions=[str(item.get("name") or "") for item in info.functions],
        )

    @cached_property
    def me(self) -> User:
        user = UserService(self.client).get_me()
        return User(
            _api=self,
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            first_name=user.first_name,
            last_name=user.last_name,
        )

    @cached_property
    def courses(self) -> CourseCollection:
        return CourseCollection(
            self, lambda: EnrolService(self.client).get_my_courses(self.site.user_id)
        )

    def course(self, key: int | str) -> Course:
        """Course by numeric id or short name (``COMP3204``)."""
        if isinstance(key, str) and key.lstrip("-").isdigit():
            key = int(key)
        if isinstance(key, str):
            return self.courses.by_short_name(key)
        record = CourseService(self.client).get_course(int(key))
        return self._course_from(record)

    def search(self, query: str) -> list[Course]:
        return [
            self._course_from(record) for record in CourseService(self.client).search_courses(query)
        ]

    def timeline(self, classification: str = "all") -> list[Course]:
        rows = CourseService(self.client).get_timeline(classification)
        return [self._course_from(record) for record in rows]

    def all_courses(self) -> list[Course]:
        return [self._course_from(record) for record in CourseService(self.client).list_courses()]

    def module(self, cmid: int) -> dict[str, Any]:
        return CourseService(self.client).get_module(cmid)

    def list_files(
        self,
        context_id: int | None = None,
        component: str = "user",
        file_area: str = "private",
        item_id: int = 0,
        file_path: str = "/",
    ) -> list[FileRef]:
        cid = int(context_id if context_id is not None else self.me.id)
        rows = FileService(self.client).list_files(cid, component, file_area, item_id, file_path)
        return [FileRef(_api=self, name=row.file_name or "", url=row.file_url) for row in rows]

    @cached_property
    def files(self) -> list[FileRef]:
        return self.list_files()

    def upcoming(self, limit: int = 50) -> list[Event]:
        rows = CalendarService(self.client).get_upcoming(limit)
        return [
            Event(
                _api=self,
                id=row.id,
                name=row.name,
                course_id=row.course_id,
                event_type=row.event_type,
                time_start=row.time_start,
                description=row.description,
            )
            for row in rows
        ]

    @cached_property
    def calendar(self) -> list[Event]:
        return self.upcoming(50)

    def unread_count(self) -> int:
        return MessageService(self.client).unread_count(self.me.id)

    @cached_property
    def messages(self) -> list[Message]:
        rows = MessageService(self.client).get_messages(self.me.id)
        return [
            Message(
                _api=self,
                id=row.id,
                from_id=row.user_id_from,
                to_id=row.user_id_to,
                text=row.text,
                time_created=row.time_created,
            )
            for row in rows
        ]

    @cached_property
    def conversations(self) -> list[Conversation]:
        rows = MessageService(self.client).get_conversations(self.me.id)
        return [
            Conversation(
                _api=self,
                id=row.id,
                name=row.name or "",
                unread=int(row.unread_count or 0),
                member_count=row.member_count,
            )
            for row in rows
        ]

    @cached_property
    def badges(self) -> list[Badge]:
        return [
            Badge(
                _api=self,
                id=row.id,
                name=row.name,
                description=row.description,
                course_id=int(row.course_id or 0),
                date_issued=row.date_issued,
                issuer=row.issuer_name,
            )
            for row in BadgeService(self.client).user_badges(self.me.id)
        ]

    @cached_property
    def categories(self) -> list[Category]:
        return [
            Category(
                _api=self,
                id=row.id,
                name=row.name,
                parent=row.parent,
                course_count=row.course_count,
                visible=row.visible,
            )
            for row in CourseService(self.client).get_categories()
        ]

    @cached_property
    def cohorts(self) -> list[Cohort]:
        return [
            Cohort(
                _api=self,
                id=row.id,
                name=row.name,
                id_number=row.id_number,
                description=row.description,
                visible=row.visible,
            )
            for row in CohortService(self.client).list_cohorts()
        ]

    def get_everything(self, *, deep: bool = False) -> dict[str, Any]:
        """Site, identity, courses, calendar, messages, badges, categories, cohorts."""
        return {
            "site": self.site.to_dict(),
            "me": self.me.to_dict(),
            "courses": [course.snapshot(deep=deep) for course in self.courses],
            "calendar": [event.to_dict() for event in self.calendar],
            "messages": [row.to_dict() for row in self.messages],
            "conversations": [row.to_dict() for row in self.conversations],
            "badges": [row.to_dict() for row in self.badges],
            "categories": [row.to_dict() for row in self.categories],
            "cohorts": [row.to_dict() for row in self.cohorts],
        }

    def dump(
        self,
        dest: str | Path,
        *,
        files: bool = True,
        deep: bool = False,
        pages: str | None = "md",
    ) -> Path:
        """Write ``site.json`` plus one folder per enrolled course."""
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        overview = {
            "site": self.site.to_dict(),
            "me": self.me.to_dict(),
            "calendar": [event.to_dict() for event in self.calendar],
            "badges": [row.to_dict() for row in self.badges],
            "categories": [row.to_dict() for row in self.categories],
            "cohorts": [row.to_dict() for row in self.cohorts],
            "courses": [
                {"id": course.id, "short_name": course.short_name, "full_name": course.full_name}
                for course in self.courses
            ],
        }
        (dest / "site.json").write_text(
            json.dumps(overview, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        for course in self.courses:
            course.dump(
                dest / safe_name(course.short_name),
                files=files,
                deep=deep,
                pages=pages,
            )
        return dest

    def _course_from(self, record: CourseRecord | Any) -> Course:
        return Course(
            _api=self,
            id=int(record.id),
            short_name=record.short_name,
            full_name=record.full_name,
            category_id=int(getattr(record, "category_id", 0) or 0),
            visible=int(getattr(record, "visible", 1) or 0),
            start_date=int(getattr(record, "start_date", 0) or 0),
            end_date=int(getattr(record, "end_date", 0) or 0),
            summary=str(getattr(record, "summary", "") or ""),
            format=str(getattr(record, "format", "topics") or "topics"),
            last_access=getattr(record, "last_access", None),
        )
