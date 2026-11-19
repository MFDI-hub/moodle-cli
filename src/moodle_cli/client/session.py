"""Moodle client that uses a browser storage-state file instead of a web-service token.

Sites that disable the mobile web service still accept the logged-in session cookie.
Requests go to ``/lib/ajax/service.php`` with that cookie and the page sesskey, which
is how the Moodle web UI calls its own web-service functions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from curl_cffi.requests.exceptions import HTTPError, RequestException

from moodle_cli.client.http import MoodleHTTPClient
from moodle_cli.client.pages import (
    activity_document,
    clean_url,
    filename,
    instance_from_html,
    is_html,
    module_bodies,
    parse_activity_intro,
    parse_assign_view,
    parse_badges,
    parse_categories,
    parse_choice_results,
    parse_cohorts,
    parse_completion,
    parse_conversations,
    parse_database,
    parse_enrol_methods,
    parse_feedback_analysis,
    parse_files,
    parse_forum_discussions,
    parse_forum_posts,
    parse_glossary,
    parse_grade_report,
    parse_groupings,
    parse_groups,
    parse_lesson,
    parse_messages,
    parse_notes,
    parse_participants,
    parse_quiz_review,
    parse_quiz_view,
    parse_wiki_page,
    parse_wiki_pages,
    parse_workshop,
    section_summary,
    text as _text,
)
from moodle_cli.client.readonly import READ_ALLOWLIST
from moodle_cli.client.storage import cookies_for_host
from moodle_cli.exceptions import (
    AuthenticationError,
    MoodleAPIError,
    MoodleConnectionError,
    ReadOnlyViolation,
)
from moodle_cli.services.content import CONTENT_FUNCTIONS

logger = logging.getLogger(__name__)

_COURSE_FALLBACK_ERRORS = frozenset(
    {"nopermissions", "errorcoursecontextnotvalid", "servicenotavailable"}
)
_ACTIVITY_KINDS = frozenset({"page", "resource", "folder", "url", "assign"})
_CALENDAR_AJAX = frozenset(
    {
        "core_calendar_get_action_events_by_timesort",
        "core_calendar_get_action_events_by_course",
    }
)
_CONTENT_KEYS = dict(CONTENT_FUNCTIONS.values())
SESSION_FUNCTIONS = sorted(
    {
        "core_webservice_get_site_info",
        "core_enrol_get_users_courses",
        "core_enrol_get_enrolled_users",
        "core_enrol_get_course_enrolment_methods",
        "core_course_get_contents",
        "core_course_get_courses",
        "core_course_get_categories",
        "core_course_get_course_module",
        "core_course_get_enrolled_courses_by_timeline_classification",
        "core_course_search_courses",
        "core_courseformat_get_state",
        "core_user_get_users_by_field",
        "core_user_get_users",
        "core_user_get_course_user_profiles",
        "core_calendar_get_action_events_by_timesort",
        "core_calendar_get_action_events_by_course",
        "core_calendar_get_calendar_events",
        "core_group_get_course_groups",
        "core_group_get_course_groupings",
        "core_group_get_course_user_groups",
        "core_completion_get_activities_completion_status",
        "core_completion_get_course_completion_status",
        "core_notes_get_course_notes",
        "core_cohort_get_cohorts",
        "core_files_get_files",
        "core_message_get_messages",
        "core_message_get_conversations",
        "core_message_get_conversation_messages",
        "core_message_get_unread_conversations_count",
        "core_badges_get_user_badges",
        "gradereport_user_get_grade_items",
        "gradereport_user_get_grades_table",
        "gradereport_overview_get_course_grades",
        "mod_assign_get_assignments",
        "mod_assign_get_submissions",
        "mod_assign_get_grades",
        "mod_assign_get_submission_status",
        "mod_forum_get_forums_by_courses",
        "mod_forum_get_forum_discussions",
        "mod_forum_get_discussion_posts",
        "mod_quiz_get_quizzes_by_courses",
        "mod_quiz_get_user_attempts",
        "mod_quiz_get_user_best_grade",
        "mod_quiz_get_attempt_review",
        "mod_feedback_get_feedbacks_by_courses",
        "mod_feedback_get_analysis",
        "mod_feedback_get_non_respondents",
        "mod_choice_get_choices_by_courses",
        "mod_choice_get_choice_results",
        "mod_workshop_get_submissions",
        "mod_workshop_get_grades_report",
        "mod_glossary_get_entries_by_letter",
        "mod_data_get_entries",
        "mod_wiki_get_subwiki_pages",
        "mod_wiki_get_page_contents",
        "mod_lesson_get_pages",
        "mod_quiz_get_attempt_data",
        "mod_feedback_get_page_items",
        "core_blog_get_entries",
        "core_comment_get_comments",
        "core_rating_get_item_ratings",
        "core_tag_get_tags",
        "core_tag_get_tagindex",
        "core_tag_get_tag_cloud",
        "core_search_get_results",
        "core_competency_list_course_competencies",
        "core_grading_get_definitions",
        "mod_chat_get_sessions",
        "mod_chat_get_session_messages",
        "mod_h5pactivity_get_attempts",
        "mod_h5pactivity_get_results",
        "mod_scorm_get_scorm_scoes",
        "mod_scorm_get_scorm_sco_tracks",
        "mod_scorm_get_scorm_attempt_count",
        "mod_survey_get_questions",
        "mod_survey_get_responses",
        *(fn for fn, _key in CONTENT_FUNCTIONS.values()),
    }
)


def extract_moodle_cfg(html: str) -> dict[str, Any]:
    """Parse the ``M.cfg`` object embedded in a logged-in Moodle page."""
    marker = html.find("M.cfg")
    if marker < 0:
        raise AuthenticationError("Moodle page did not include a session config.")
    start = html.find("{", marker)
    if start < 0:
        raise AuthenticationError("Moodle page did not include a session config.")
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(html[start:], start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(html[start : index + 1])
                except json.JSONDecodeError as exc:
                    raise AuthenticationError("Could not parse the Moodle session config.") from exc
                if not isinstance(parsed, dict):
                    raise AuthenticationError("Moodle session config was not an object.")
                return parsed
    raise AuthenticationError("Moodle session config was truncated.")


def course_record(course: dict[str, Any]) -> dict[str, Any]:
    """Normalize a timeline/recent course into the fields the course and enrol models use."""
    visible = course.get("visible", 1)
    if isinstance(visible, bool):
        visible = int(visible)
    category = course.get("categoryid", course.get("coursecategory", 0))
    try:
        category_id = int(category)
    except (TypeError, ValueError):
        category_id = 0
    progress = course.get("progress")
    if isinstance(progress, bool) or not isinstance(progress, (int, float)):
        progress = None
    return {
        "id": int(course["id"]),
        "shortname": _text(course.get("shortname")),
        "fullname": _text(course.get("fullname")),
        "categoryid": category_id,
        "summary": _text(course.get("summary")),
        "visible": int(visible or 0),
        "format": course.get("format") or "topics",
        "startdate": int(course.get("startdate") or 0),
        "enddate": int(course.get("enddate") or 0),
        "enrolledusercount": int(course.get("enrolledusercount") or 0),
        "progress": progress,
        "lastaccess": course.get("lastaccess"),
        "completed": course.get("completed"),
    }


def sections_from_state(state: Any) -> list[dict[str, Any]]:
    """Turn a ``core_courseformat_get_state`` payload into course-content sections."""
    if isinstance(state, str):
        state = json.loads(state)
    if not isinstance(state, dict):
        raise MoodleAPIError("Unexpected course state response.")
    modules = {
        int(cm["id"]): cm for cm in state.get("cm") or [] if isinstance(cm, dict) and "id" in cm
    }
    sections: list[dict[str, Any]] = []
    for section in state.get("section") or []:
        if not isinstance(section, dict):
            continue
        name = _text(section.get("rawtitle") or section.get("title"))
        if not name:
            name = f"Section {section.get('number', '')}".strip()
        cms: list[dict[str, Any]] = []
        for cmid in section.get("cmlist") or []:
            cm = modules.get(int(cmid))
            if cm is None:
                continue
            cms.append(
                {
                    "id": int(cm["id"]),
                    "name": _text(cm.get("name")),
                    "modname": cm.get("modname") or "",
                    "url": cm.get("url") or "",
                    "visible": int(bool(cm.get("accessvisible", 1))),
                }
            )
        sections.append(
            {
                "id": int(section.get("id") or 0),
                "name": name,
                "summary": "",
                "modules": cms,
            }
        )
    return sections


def calendar_event(event: dict[str, Any]) -> dict[str, Any]:
    """Normalize an action-event payload into the calendar model fields."""
    raw_course = event.get("course")
    course: dict[str, Any] = raw_course if isinstance(raw_course, dict) else {}
    course_id = int(event.get("courseid") or course.get("id") or 0)
    return {
        "id": int(event.get("id") or 0),
        "name": _text(event.get("name")),
        "description": _text(event.get("description") or event.get("formatteddescription")),
        "eventtype": str(event.get("eventtype") or event.get("component") or ""),
        "courseid": course_id,
        "timestart": int(event.get("timestart") or event.get("timesort") or 0),
        "timeduration": int(event.get("timeduration") or 0),
    }


class MoodleSessionClient(MoodleHTTPClient):
    """Call Moodle with cookies from a Playwright storage-state file."""

    def __init__(
        self,
        base_url: str,
        storage_state: Path,
        timeout: float = 30.0,
        readonly: bool = False,
    ) -> None:
        super().__init__(base_url, token="", timeout=timeout, readonly=readonly)
        self.storage_state = Path(storage_state)
        if not self.storage_state.is_file():
            raise AuthenticationError(f"Storage state not found: {self.storage_state}")
        for cookie in cookies_for_host(self.storage_state, self.base_url):
            self.session.cookies.set(
                str(cookie["name"]),
                str(cookie["value"]),
                domain=str(cookie.get("domain") or ""),
                path=str(cookie.get("path") or "/"),
            )
        self.sesskey = ""
        self.user_id = 0
        self._ready = False
        self._states: dict[int, dict[str, Any]] = {}
        self._cm_cache: dict[tuple[str, int], dict[str, Any]] = {}
        self._instances: dict[tuple[str, int], dict[str, Any]] = {}

    def call(self, wsfunction: str, **params: Any) -> Any:
        """Call a web-service function through the logged-in AJAX endpoint."""
        if self.readonly and wsfunction not in READ_ALLOWLIST:
            raise ReadOnlyViolation(
                f"Read-only mode: web-service function '{wsfunction}' is not in the read "
                f"allowlist. moodle-readonly refuses any operation that could mutate the site."
            )
        from moodle_cli._utils import redact

        logger.debug("AJAX %s %s", wsfunction, redact(params))
        if wsfunction == "core_webservice_get_site_info":
            return self._site_info()
        if wsfunction == "core_enrol_get_users_courses":
            return self._enrolled_courses()
        if wsfunction == "core_course_get_contents":
            return self._contents(int(params["courseid"]))
        try:
            result = self._ajax(wsfunction, params)
        except MoodleAPIError as exc:
            if (
                wsfunction == "core_course_get_courses"
                and exc.error_code in _COURSE_FALLBACK_ERRORS
            ):
                return self._courses_for(params)
            if exc.error_code == "servicenotavailable":
                fallback = self._fallback(wsfunction, params)
                if fallback is not None:
                    return fallback
            raise
        if wsfunction == "core_course_get_enrolled_courses_by_timeline_classification":
            return self._normalize_timeline(result)
        if wsfunction in _CALENDAR_AJAX:
            return self._normalize_calendar(result)
        return result

    def _ensure(self) -> None:
        if self._ready:
            return
        try:
            resp = self.session.get(f"{self.base_url}/my/")
            resp.raise_for_status()
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "error"
            raise MoodleConnectionError(f"HTTP {status} from {self.base_url}") from exc
        except RequestException as exc:
            raise MoodleConnectionError(f"Could not connect to {self.base_url}: {exc}") from exc
        if "/login/" in str(getattr(resp, "url", "")):
            raise AuthenticationError(
                "Saved session is expired or signed out. Sign in again and save a new storage state."
            )
        cfg = extract_moodle_cfg(resp.text)
        user_id = int(cfg.get("userId") or 0)
        sesskey = str(cfg.get("sesskey") or "")
        if not user_id or not sesskey:
            raise AuthenticationError(
                "Saved session is expired or signed out. Sign in again and save a new storage state."
            )
        self.user_id = user_id
        self.sesskey = sesskey
        self._ready = True

    def _ajax(self, wsfunction: str, args: dict[str, Any]) -> Any:
        self._ensure()
        payload = [{"index": 0, "methodname": wsfunction, "args": args}]
        return self._unwrap(
            self._post(
                f"{self.base_url}/lib/ajax/service.php",
                {"sesskey": self.sesskey, "info": wsfunction},
                payload,
            )
        )

    def _public_config(self) -> dict[str, Any]:
        payload = [{"index": 0, "methodname": "tool_mobile_get_public_config", "args": {}}]
        data = self._unwrap(
            self._post(
                f"{self.base_url}/lib/ajax/service-nologin.php",
                {"info": "tool_mobile_get_public_config"},
                payload,
            )
        )
        return data if isinstance(data, dict) else {}

    def _post(self, url: str, params: dict[str, str], payload: list[dict[str, Any]]) -> Any:
        try:
            resp = self.session.post(url, params=params, json=payload)
            resp.raise_for_status()
        except HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "error"
            raise MoodleConnectionError(f"HTTP {status} from {self.base_url}") from exc
        except RequestException as exc:
            raise MoodleConnectionError(f"Could not connect to {self.base_url}: {exc}") from exc
        return resp.json()

    def _unwrap(self, data: Any) -> Any:
        if not isinstance(data, list) or not data:
            raise MoodleAPIError("Unexpected response from Moodle.", error_code="invalidresponse")
        item = data[0]
        if not isinstance(item, dict):
            raise MoodleAPIError("Unexpected response from Moodle.", error_code="invalidresponse")
        if item.get("error"):
            exc = item.get("exception") or {}
            code = exc.get("errorcode")
            message = exc.get("message") or "Moodle request failed"
            if code == "servicenotavailable":
                message += " This function is not exposed to a browser session."
            raise MoodleAPIError(message, error_code=code, debug_info=exc.get("debuginfo"))
        return item.get("data")

    def _site_info(self) -> dict[str, Any]:
        self._ensure()
        users = self._ajax(
            "core_user_get_users_by_field", {"field": "id", "values": [str(self.user_id)]}
        )
        user = users[0] if isinstance(users, list) and users else {}
        try:
            public = self._public_config()
        except (MoodleAPIError, MoodleConnectionError):
            public = {}
        return {
            "sitename": public.get("sitename") or "",
            "siteurl": public.get("wwwroot") or self.base_url,
            "username": user.get("username") or "",
            "fullname": user.get("fullname") or "",
            "userid": int(user.get("id") or self.user_id),
            "firstname": user.get("firstname") or "",
            "lastname": user.get("lastname") or "",
            "lang": user.get("lang") or public.get("lang") or "",
            "release": "",
            "version": "",
            "functions": [{"name": name, "version": ""} for name in SESSION_FUNCTIONS],
        }

    def _normalize_timeline(self, page: Any) -> dict[str, Any]:
        if not isinstance(page, dict):
            return {"courses": [], "nextoffset": 0}
        courses = [
            course_record(item) for item in page.get("courses") or [] if isinstance(item, dict)
        ]
        return {**page, "courses": courses}

    def _normalize_calendar(self, page: Any) -> dict[str, Any]:
        if not isinstance(page, dict):
            return {"events": []}
        events = [
            calendar_event(item) for item in page.get("events") or [] if isinstance(item, dict)
        ]
        return {**page, "events": events}

    def _enrolled_courses(self) -> list[dict[str, Any]]:
        return [course_record(course) for course in self._timeline("all")]

    def _courses_for(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        courses = [course_record(course) for course in self._timeline("all")]
        options = params.get("options") or {}
        raw_ids = options.get("ids") if isinstance(options, dict) else None
        if not raw_ids:
            return courses
        wanted = {int(course_id) for course_id in raw_ids}
        found = [course for course in courses if course["id"] in wanted]
        if len(found) != len(wanted):
            missing = sorted(wanted - {course["id"] for course in found})
            raise MoodleAPIError(
                f"Course not in this session: {', '.join(str(course_id) for course_id in missing)}",
                error_code="invalidrecord",
            )
        return found

    def _timeline(self, classification: str) -> list[dict[str, Any]]:
        courses: list[dict[str, Any]] = []
        offset = 0
        limit = 100
        while True:
            page = self._ajax(
                "core_course_get_enrolled_courses_by_timeline_classification",
                {"classification": classification, "limit": limit, "offset": offset},
            )
            batch = page.get("courses") if isinstance(page, dict) else None
            if not isinstance(batch, list) or not batch:
                break
            courses.extend(item for item in batch if isinstance(item, dict))
            nxt = page.get("nextoffset") if isinstance(page, dict) else None
            if not isinstance(nxt, int) or nxt <= offset or len(batch) < limit:
                break
            offset = nxt
        return courses

    def _fallback(self, wsfunction: str, params: dict[str, Any]) -> Any:
        if wsfunction in _CONTENT_KEYS:
            return self._content_list(wsfunction, params)
        handlers = {
            "gradereport_user_get_grade_items": self._grade_items,
            "gradereport_user_get_grades_table": self._grade_table,
            "gradereport_overview_get_course_grades": self._grade_overview,
            "mod_assign_get_assignments": self._assignments,
            "mod_assign_get_submissions": self._assign_submissions,
            "mod_assign_get_grades": self._assign_grades,
            "mod_assign_get_submission_status": self._assign_status,
            "mod_forum_get_forums_by_courses": self._forums,
            "mod_forum_get_forum_discussions": self._forum_discussions,
            "mod_forum_get_discussion_posts": self._forum_posts,
            "mod_quiz_get_quizzes_by_courses": self._quizzes,
            "mod_quiz_get_user_attempts": self._quiz_attempts,
            "mod_quiz_get_user_best_grade": self._quiz_best,
            "mod_quiz_get_attempt_review": self._quiz_review,
            "core_enrol_get_enrolled_users": self._participants,
            "core_enrol_get_course_enrolment_methods": self._enrol_methods,
            "core_user_get_users": self._users,
            "core_user_get_course_user_profiles": self._course_profiles,
            "core_group_get_course_groups": self._groups,
            "core_group_get_course_groupings": self._groupings,
            "core_group_get_course_user_groups": self._user_groups,
            "core_completion_get_activities_completion_status": self._completion,
            "core_completion_get_course_completion_status": self._course_completion,
            "core_course_get_categories": self._categories,
            "core_course_get_course_module": self._course_module,
            "core_calendar_get_calendar_events": self._calendar_events,
            "core_message_get_messages": self._messages,
            "core_message_get_conversations": self._conversations,
            "core_message_get_conversation_messages": self._conversation_messages,
            "core_message_get_unread_conversations_count": self._unread_count,
            "core_badges_get_user_badges": self._badges,
            "core_files_get_files": self._files,
            "core_notes_get_course_notes": self._notes,
            "core_cohort_get_cohorts": self._cohorts,
            "mod_feedback_get_feedbacks_by_courses": self._feedbacks,
            "mod_feedback_get_analysis": self._feedback_analysis,
            "mod_feedback_get_non_respondents": self._non_respondents,
            "mod_choice_get_choices_by_courses": self._choices,
            "mod_choice_get_choice_results": self._choice_results,
            "mod_workshop_get_submissions": self._workshop_submissions,
            "mod_workshop_get_grades_report": self._workshop_grades,
            "mod_glossary_get_entries_by_letter": self._glossary,
            "mod_data_get_entries": self._database,
            "mod_wiki_get_subwiki_pages": self._wiki_pages,
            "mod_wiki_get_page_contents": self._wiki_page,
            "mod_lesson_get_pages": self._lesson,
        }
        handler = handlers.get(wsfunction)
        if handler is None:
            return None
        return handler(params)

    def _course_ids(self, params: dict[str, Any]) -> list[int]:
        raw = params.get("courseids", params.get("courseid"))
        if raw is None:
            return [int(course["id"]) for course in self._timeline("all")]
        if isinstance(raw, list):
            return [int(item) for item in raw]
        return [int(raw)]

    def _course_state(self, course_id: int) -> dict[str, Any]:
        if course_id not in self._states:
            state = self._ajax("core_courseformat_get_state", {"courseid": course_id})
            if isinstance(state, str):
                state = json.loads(state)
            self._states[course_id] = state if isinstance(state, dict) else {}
        return self._states[course_id]

    def _cms(self, course_id: int, module: str | None = None) -> list[dict[str, Any]]:
        cms: list[dict[str, Any]] = []
        for cm in self._course_state(course_id).get("cm") or []:
            if not isinstance(cm, dict) or "id" not in cm:
                continue
            kind = str(cm.get("module") or "")
            if module and kind != module:
                continue
            cmid = int(cm["id"])
            cms.append(
                {
                    "id": cmid,
                    "name": _text(cm.get("name")),
                    "module": kind,
                    "modname": cm.get("modname") or "",
                    "url": cm.get("url") or f"{self.base_url}/mod/{kind}/view.php?id={cmid}",
                    "visible": int(bool(cm.get("accessvisible", 1))),
                    "sectionid": int(cm.get("sectionid") or 0),
                    "course": course_id,
                }
            )
        return cms

    def _html(self, url: str) -> str:
        resp = self._open(url)
        if resp is None or not is_html(resp):
            raise MoodleAPIError(
                "This session cannot open that page.",
                error_code="nopermissions",
            )
        return resp.text

    def _cm_detail(self, module: str, cmid: int, course_id: int = 0) -> dict[str, Any]:
        key = (module, cmid)
        if key in self._cm_cache:
            return self._cm_cache[key]
        page_html = self._html(f"{self.base_url}/mod/{module}/view.php?id={cmid}")
        instance = instance_from_html(page_html, module, cmid)
        if module == "assign":
            detail = parse_assign_view(page_html, cmid, course_id)
        elif module == "quiz":
            detail = parse_quiz_view(page_html, instance, course_id)
            detail["cmid"] = cmid
            detail["instance"] = instance
            detail["id"] = instance
            detail["coursemodule"] = cmid
        else:
            detail = parse_activity_intro(page_html, module, cmid, course_id)
        detail["_html"] = page_html
        detail["cmid"] = int(detail.get("cmid") or cmid)
        detail["instance"] = int(detail.get("instance") or instance)
        detail["url"] = f"{self.base_url}/mod/{module}/view.php?id={cmid}"
        if not detail.get("course"):
            detail["course"] = course_id
        self._cm_cache[key] = detail
        self._instances[(module, int(detail["instance"]))] = detail
        return detail

    def _activity_lookup(self, module: str, ident: int) -> dict[str, Any]:
        cached = self._instances.get((module, ident)) or self._cm_cache.get((module, ident))
        if cached:
            return cached
        try:
            return self._cm_detail(module, ident)
        except MoodleAPIError:
            pass
        for course in self._timeline("all"):
            course_id = int(course["id"])
            for cm in self._cms(course_id, module):
                try:
                    detail = self._cm_detail(module, cm["id"], course_id)
                except MoodleAPIError:
                    continue
                if int(detail.get("instance") or 0) == ident or cm["id"] == ident:
                    return detail
        raise MoodleAPIError(
            f"{module} {ident} not in this session.",
            error_code="invalidrecord",
        )

    def _grade_items(self, params: dict[str, Any]) -> dict[str, Any]:
        course_id = int(params["courseid"])
        user_id = int(params.get("userid") or self.user_id)
        items = parse_grade_report(
            self._html(
                f"{self.base_url}/grade/report/user/index.php?id={course_id}&userid={user_id}"
            )
        )
        return {
            "usergrades": [
                {
                    "userid": user_id,
                    "courseid": course_id,
                    "userfullname": "",
                    "gradeitems": items,
                }
            ]
        }

    def _grade_table(self, params: dict[str, Any]) -> dict[str, Any]:
        report = self._grade_items(params)
        user = report["usergrades"][0]
        tabledata = [
            {
                "itemname": {"content": item.get("itemname") or ""},
                "grade": {"content": item.get("grade") or ""},
            }
            for item in user["gradeitems"]
        ]
        return {
            "tables": [
                {
                    "userid": user["userid"],
                    "userfullname": user["userfullname"],
                    "tabledata": tabledata,
                }
            ]
        }

    def _grade_overview(self, _params: dict[str, Any]) -> dict[str, Any]:
        grades: list[dict[str, Any]] = []
        for course in self._timeline("all"):
            course_id = int(course["id"])
            items = self._grade_items({"courseid": course_id})["usergrades"][0]["gradeitems"]
            total = next(
                (
                    item
                    for item in reversed(items)
                    if "total" in str(item.get("itemname") or "").lower()
                ),
                items[-1] if items else None,
            )
            grades.append(
                {
                    "courseid": course_id,
                    "grade": (total or {}).get("grade") or "",
                    "rawgrade": (total or {}).get("grade") or "",
                }
            )
        return {"grades": grades}

    def _assignments(self, params: dict[str, Any]) -> dict[str, Any]:
        assignments: list[dict[str, Any]] = []
        for course_id in self._course_ids(params):
            for cm in self._cms(course_id, "assign"):
                try:
                    detail = self._cm_detail("assign", cm["id"], course_id)
                except MoodleAPIError:
                    detail = {"instance": cm["id"], "duedate": 0, "grade": 0, "name": cm["name"]}
                assignments.append(
                    {
                        "id": int(detail.get("instance") or cm["id"]),
                        "cmid": cm["id"],
                        "course": course_id,
                        "name": detail.get("name") or cm["name"],
                        "duedate": int(detail.get("duedate") or 0),
                        "grade": detail.get("grade") or 0,
                    }
                )
        return {"courses": [{"id": 0, "assignments": assignments}]}

    def _assign_submissions(self, params: dict[str, Any]) -> dict[str, Any]:
        assignments: list[dict[str, Any]] = []
        for assign_id in params.get("assignmentids") or []:
            detail = self._activity_lookup("assign", int(assign_id))
            status = detail.get("status") or {}
            assignments.append(
                {
                    "assignmentid": int(detail.get("instance") or assign_id),
                    "submissions": [
                        {
                            "id": int(detail.get("instance") or assign_id),
                            "userid": self.user_id,
                            "status": status.get("status") or "new",
                            "timemodified": 0,
                            "gradingstatus": status.get("gradingstatus") or "notgraded",
                        }
                    ],
                }
            )
        return {"assignments": assignments}

    def _assign_grades(self, params: dict[str, Any]) -> dict[str, Any]:
        assignments: list[dict[str, Any]] = []
        for assign_id in params.get("assignmentids") or []:
            detail = self._activity_lookup("assign", int(assign_id))
            grade = detail.get("gradevalue") or ""
            assignments.append(
                {
                    "assignmentid": int(detail.get("instance") or assign_id),
                    "grades": [{"userid": self.user_id, "grade": grade}] if grade else [],
                }
            )
        return {"assignments": assignments}

    def _assign_status(self, params: dict[str, Any]) -> dict[str, Any]:
        detail = self._activity_lookup("assign", int(params["assignid"]))
        status = detail.get("status") or {}
        return {
            "lastattempt": {
                "submission": {
                    "id": int(detail.get("instance") or params["assignid"]),
                    "userid": int(params.get("userid") or self.user_id),
                    "status": status.get("status") or "new",
                    "timemodified": 0,
                    "gradingstatus": status.get("gradingstatus") or "notgraded",
                }
            },
            "feedback": {"grade": {"grade": detail.get("gradevalue") or "-"}},
            "files": detail.get("files") or [],
        }

    def _forums(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        forums: list[dict[str, Any]] = []
        for course_id in self._course_ids(params):
            for cm in self._cms(course_id, "forum"):
                try:
                    detail = self._cm_detail("forum", cm["id"], course_id)
                except MoodleAPIError:
                    detail = {"instance": cm["id"], "intro": "", "name": cm["name"]}
                forums.append(
                    {
                        "id": int(detail.get("instance") or cm["id"]),
                        "course": course_id,
                        "name": detail.get("name") or cm["name"],
                        "type": "general",
                        "intro": detail.get("intro") or "",
                        "numdiscussions": 0,
                        "cmid": cm["id"],
                    }
                )
        return forums

    def _forum_discussions(self, params: dict[str, Any]) -> dict[str, Any]:
        detail = self._activity_lookup("forum", int(params["forumid"]))
        return {
            "discussions": parse_forum_discussions(
                str(detail.get("_html") or ""), int(detail.get("instance") or 0)
            )
        }

    def _forum_posts(self, params: dict[str, Any]) -> dict[str, Any]:
        discussion_id = int(params["discussionid"])
        return {
            "posts": parse_forum_posts(
                self._html(f"{self.base_url}/mod/forum/discuss.php?d={discussion_id}"),
                discussion_id,
            )
        }

    def _quizzes(self, params: dict[str, Any]) -> dict[str, Any]:
        quizzes: list[dict[str, Any]] = []
        for course_id in self._course_ids(params):
            for cm in self._cms(course_id, "quiz"):
                try:
                    detail = self._cm_detail("quiz", cm["id"], course_id)
                except MoodleAPIError:
                    detail = {"instance": cm["id"], "name": cm["name"], "grade": 0}
                quizzes.append(
                    {
                        "id": int(detail.get("instance") or cm["id"]),
                        "course": course_id,
                        "coursemodule": cm["id"],
                        "name": detail.get("name") or cm["name"],
                        "timeopen": 0,
                        "timeclose": 0,
                        "grade": detail.get("grade") or 0,
                    }
                )
        return {"quizzes": quizzes}

    def _quiz_attempts(self, params: dict[str, Any]) -> dict[str, Any]:
        detail = self._activity_lookup("quiz", int(params["quizid"]))
        attempts = list(detail.get("attempts") or [])
        for attempt in attempts:
            attempt["userid"] = int(params.get("userid") or self.user_id)
            attempt["quiz"] = int(detail.get("instance") or params["quizid"])
        return {"attempts": attempts}

    def _quiz_best(self, params: dict[str, Any]) -> dict[str, Any]:
        detail = self._activity_lookup("quiz", int(params["quizid"]))
        return {"hasgrade": bool(detail.get("hasgrade")), "grade": detail.get("grade")}

    def _quiz_review(self, params: dict[str, Any]) -> dict[str, Any]:
        attempt_id = int(params["attemptid"])
        return parse_quiz_review(
            self._html(f"{self.base_url}/mod/quiz/review.php?attempt={attempt_id}"),
            attempt_id,
        )

    def _participants(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        course_id = int(params["courseid"])
        return parse_participants(
            self._html(f"{self.base_url}/user/index.php?id={course_id}"), course_id
        )

    def _enrol_methods(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        course_id = int(params["courseid"])
        return parse_enrol_methods(
            self._html(f"{self.base_url}/enrol/index.php?id={course_id}"), course_id
        )

    def _users(self, params: dict[str, Any]) -> dict[str, Any]:
        criteria = params.get("criteria") or []
        first = criteria[0] if criteria and isinstance(criteria[0], dict) else {}
        key = str(first.get("key") or "email")
        value = str(first.get("value") or "")
        if key in {"id", "username", "email"} and value:
            try:
                users = self._ajax(
                    "core_user_get_users_by_field", {"field": key, "values": [value]}
                )
            except MoodleAPIError:
                users = []
            if isinstance(users, list):
                return {"users": users}
        return {"users": []}

    def _course_profiles(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        userlist = params.get("userlist") or []
        if not userlist:
            return []
        course_id = int(userlist[0]["courseid"])
        wanted = {int(item["userid"]) for item in userlist}
        return [
            user for user in self._participants({"courseid": course_id}) if user["id"] in wanted
        ]

    def _groups(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        course_id = int(params["courseid"])
        return parse_groups(
            self._html(f"{self.base_url}/group/index.php?id={course_id}"), course_id
        )

    def _groupings(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        course_id = int(params["courseid"])
        return parse_groupings(
            self._html(f"{self.base_url}/group/groupings.php?id={course_id}"), course_id
        )

    def _user_groups(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"groups": self._groups(params)}

    def _completion(self, params: dict[str, Any]) -> dict[str, Any]:
        course_id = int(params["courseid"])
        try:
            statuses = parse_completion(
                self._html(f"{self.base_url}/report/progress/index.php?course={course_id}")
            )
        except MoodleAPIError:
            statuses = []
        if not statuses:
            statuses = [
                {
                    "cmid": cm["id"],
                    "modname": cm["module"],
                    "instance": 0,
                    "state": 0,
                    "timecompleted": 0,
                    "tracking": 0,
                }
                for cm in self._cms(course_id)
            ]
        return {"statuses": statuses}

    def _course_completion(self, params: dict[str, Any]) -> dict[str, Any]:
        statuses = self._completion(params)["statuses"]
        completed = bool(statuses) and all(item.get("state") for item in statuses)
        return {
            "completionstatus": {
                "completed": completed,
                "aggregation": 1,
                "completions": statuses,
            }
        }

    def _categories(self, _params: dict[str, Any]) -> list[dict[str, Any]]:
        return parse_categories(self._html(f"{self.base_url}/course/index.php"))

    def _course_module(self, params: dict[str, Any]) -> dict[str, Any]:
        cmid = int(params["cmid"])
        for course in self._timeline("all"):
            for cm in self._cms(int(course["id"])):
                if cm["id"] != cmid:
                    continue
                return {
                    "cm": {
                        "id": cmid,
                        "name": cm["name"],
                        "modname": cm["module"],
                        "instance": cmid,
                        "course": cm["course"],
                        "section": cm["sectionid"],
                        "visible": cm["visible"],
                        "url": cm["url"],
                    }
                }
        raise MoodleAPIError(
            f"Course module {cmid} not in this session.", error_code="invalidrecord"
        )

    def _calendar_events(self, params: dict[str, Any]) -> dict[str, Any]:
        events_filter = params.get("events") if isinstance(params.get("events"), dict) else {}
        course_ids = events_filter.get("courseids") if isinstance(events_filter, dict) else None
        collected: list[dict[str, Any]] = []
        if course_ids:
            for course_id in course_ids:
                page = self._ajax(
                    "core_calendar_get_action_events_by_course", {"courseid": int(course_id)}
                )
                collected.extend(self._normalize_calendar(page)["events"])
        else:
            page = self._ajax("core_calendar_get_action_events_by_timesort", {"limitnum": 50})
            collected = self._normalize_calendar(page)["events"]
        return {"events": collected}

    def _messages(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {"messages": parse_messages(self._html(f"{self.base_url}/message/index.php"))}

    def _conversations(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {
            "conversations": parse_conversations(self._html(f"{self.base_url}/message/index.php"))
        }

    def _conversation_messages(self, _params: dict[str, Any]) -> dict[str, Any]:
        return self._messages(_params)

    def _unread_count(self, _params: dict[str, Any]) -> int:
        conversations = self._conversations(_params).get("conversations") or []
        return sum(int(item.get("unreadcount") or 0) for item in conversations)

    def _badges(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {"badges": parse_badges(self._html(f"{self.base_url}/badges/mybadges.php"))}

    def _files(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {"files": parse_files(self._html(f"{self.base_url}/user/files.php"), self.base_url)}

    def _notes(self, params: dict[str, Any]) -> dict[str, Any]:
        course_id = int(params["courseid"])
        return {
            "coursenotes": parse_notes(
                self._html(
                    f"{self.base_url}/notes/index.php?filtertype=course&filterselect={course_id}"
                ),
                course_id,
            )
        }

    def _cohorts(self, _params: dict[str, Any]) -> list[dict[str, Any]]:
        return parse_cohorts(self._html(f"{self.base_url}/cohort/index.php"))

    def _feedbacks(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._mod_list("feedback", params, "feedbacks")

    def _choices(self, params: dict[str, Any]) -> dict[str, Any]:
        return self._mod_list("choice", params, "choices")

    def _non_respondents(self, _params: dict[str, Any]) -> dict[str, Any]:
        return {"users": []}

    def _mod_list(self, module: str, params: dict[str, Any], key: str) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        for course_id in self._course_ids(params):
            for cm in self._cms(course_id, module):
                items.append(
                    {
                        "id": cm["id"],
                        "course": course_id,
                        "coursemodule": cm["id"],
                        "name": cm["name"],
                        "intro": "",
                        "visible": cm["visible"],
                    }
                )
        return {key: items}

    def _content_list(self, wsfunction: str, params: dict[str, Any]) -> dict[str, Any]:
        key = _CONTENT_KEYS[wsfunction]
        module = next(mod for mod, (fn, _key) in CONTENT_FUNCTIONS.items() if fn == wsfunction)
        return self._mod_list(module, params, key)

    def _feedback_analysis(self, params: dict[str, Any]) -> dict[str, Any]:
        detail = self._activity_lookup("feedback", int(params["feedbackid"]))
        parsed = parse_feedback_analysis(str(detail.get("_html") or ""))
        return parsed

    def _choice_results(self, params: dict[str, Any]) -> dict[str, Any]:
        detail = self._activity_lookup("choice", int(params["choiceid"]))
        return {"options": parse_choice_results(str(detail.get("_html") or ""))}

    def _workshop_submissions(self, params: dict[str, Any]) -> dict[str, Any]:
        detail = self._activity_lookup("workshop", int(params["workshopid"]))
        return {"submissions": parse_workshop(str(detail.get("_html") or ""))}

    def _workshop_grades(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"report": {"grades": self._workshop_submissions(params)["submissions"]}}

    def _glossary(self, params: dict[str, Any]) -> dict[str, Any]:
        detail = self._activity_lookup("glossary", int(params["id"]))
        return {"entries": parse_glossary(str(detail.get("_html") or ""))}

    def _database(self, params: dict[str, Any]) -> dict[str, Any]:
        detail = self._activity_lookup("data", int(params["databaseid"]))
        return {"entries": parse_database(str(detail.get("_html") or ""))}

    def _wiki_pages(self, params: dict[str, Any]) -> dict[str, Any]:
        page_html = self._html(f"{self.base_url}/mod/wiki/view.php?id={int(params['subwikiid'])}")
        pages = parse_wiki_pages(page_html)
        if not pages:
            detail = self._activity_lookup("wiki", int(params["subwikiid"]))
            pages = parse_wiki_pages(str(detail.get("_html") or ""))
        return {"pages": pages}

    def _wiki_page(self, params: dict[str, Any]) -> dict[str, Any]:
        page_id = int(params["pageid"])
        return {
            "page": parse_wiki_page(
                self._html(f"{self.base_url}/mod/wiki/view.php?pageid={page_id}"), page_id
            )
        }

    def _lesson(self, params: dict[str, Any]) -> dict[str, Any]:
        detail = self._activity_lookup("lesson", int(params["lessonid"]))
        return {"pages": parse_lesson(str(detail.get("_html") or ""))}

    def _contents(self, course_id: int) -> list[dict[str, Any]]:
        state = self._course_state(course_id)
        sections = sections_from_state(state)
        kinds: dict[int, str] = {}
        for cm in state.get("cm") or []:
            if isinstance(cm, dict) and "id" in cm:
                kinds[int(cm["id"])] = str(cm.get("module") or "")
        for section in sections:
            self._fill_section(section, kinds)
        return sections

    def _fill_section(self, section: dict[str, Any], kinds: dict[int, str]) -> None:
        """Add the section summary, label text, page text, and file or URL targets."""
        section_id = int(section.get("id") or 0)
        if section_id:
            page = self._open(f"{self.base_url}/course/section.php?id={section_id}")
            if page is not None and is_html(page):
                summary, links, table = section_summary(page.text, self.base_url)
                if summary:
                    section["summary"] = summary
                if table:
                    section["table"] = table
                known = {str(mod.get("url") or "") for mod in section["modules"]}
                bodies = module_bodies(page.text)
                for mod in section["modules"]:
                    text = bodies.get(int(mod["id"]))
                    if text:
                        mod["text"] = text
                for link in links:
                    if "/mod/" in link["url"] or link["url"] in known:
                        continue
                    known.add(link["url"])
                    section["modules"].append(
                        {
                            "id": 0,
                            "name": link["name"],
                            "modname": "link",
                            "url": link["url"],
                            "visible": 1,
                        }
                    )
        for mod in section["modules"]:
            if kinds.get(int(mod["id"])) not in _ACTIVITY_KINDS:
                continue
            detail = self._activity(str(mod.get("url") or ""))
            if detail.get("text"):
                mod["text"] = detail["text"]
            if detail.get("files"):
                files = list(detail["files"])
                if kinds.get(int(mod["id"])) == "assign":
                    files = [
                        item
                        for item in files
                        if "/assignsubmission_" not in str(item.get("url") or "")
                    ]
                if files:
                    mod["files"] = files
            if detail.get("target"):
                mod["target"] = detail["target"]

    def _activity(self, url: str) -> dict[str, Any]:
        if not url:
            return {}
        resp = self._open(url, follow=False)
        if resp is None:
            return {}
        status = int(getattr(resp, "status_code", 0))
        if status in {301, 302, 303, 307, 308}:
            location = clean_url(str(resp.headers.get("location") or ""), url)
            if not location.startswith(("http://", "https://")):
                return {}
            return {"files": [{"name": filename(location), "url": location}]}
        if is_html(resp):
            return activity_document(resp.text, self.base_url)
        final = clean_url(str(getattr(resp, "url", url) or url), url)
        disposition = str(resp.headers.get("content-disposition") or "")
        return {"files": [{"name": filename(final, disposition), "url": final}]}

    def _open(self, url: str, *, follow: bool = True) -> Any:
        self._ensure()
        try:
            resp = self.session.get(url, allow_redirects=follow)
        except RequestException:
            return None
        status = int(getattr(resp, "status_code", 0))
        if status >= 400:
            return None
        location = str(resp.headers.get("location") or "")
        final = str(getattr(resp, "url", ""))
        if "/login/" in final or "/login/" in location:
            return None
        return resp
