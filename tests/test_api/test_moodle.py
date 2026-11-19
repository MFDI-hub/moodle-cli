"""Tests for the lazy Moodle object API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from moodle_cli.api import Moodle
from moodle_cli.client.exceptions import MoodleAPIError

if TYPE_CHECKING:
    from pathlib import Path


RESPONSES: dict[str, Any] = {
    "core_webservice_get_site_info": {
        "sitename": "ECS",
        "siteurl": "https://moodle.example.com",
        "username": "mf",
        "fullname": "Mehmet",
        "userid": 7,
        "lang": "en",
        "release": "",
        "version": "",
        "functions": [{"name": "core_course_get_contents"}],
    },
    "core_enrol_get_users_courses": [
        {"id": 831, "shortname": "COMP3204", "fullname": "Vision", "visible": 1}
    ],
    "core_course_get_courses": [
        {
            "id": 831,
            "shortname": "COMP3204",
            "fullname": "Vision",
            "categoryid": 57,
            "visible": 1,
            "summary": "Computer vision",
            "format": "topics",
        }
    ],
    "core_course_get_contents": [
        {
            "id": 1,
            "name": "Schedule",
            "summary": "Notes",
            "table": [{"Week": "1", "Topic": "Intro"}],
            "modules": [
                {
                    "id": 10,
                    "name": "Lecture 1 (Slides)",
                    "modname": "link",
                    "url": "https://sharepoint.example/slides",
                    "visible": 1,
                },
                {
                    "id": 12,
                    "name": "About this module",
                    "modname": "page",
                    "url": "https://moodle.example.com/mod/page/view.php?id=12",
                    "visible": 1,
                    "text": "Read the handbook.",
                },
                {
                    "id": 11,
                    "name": "CW1",
                    "modname": "Assignment",
                    "url": "https://moodle.example.com/mod/assign/view.php?id=11",
                    "visible": 1,
                    "files": [
                        {
                            "name": "COMP3204-CW1.pdf",
                            "url": "https://moodle.example.com/pluginfile.php/1/COMP3204-CW1.pdf",
                        },
                        {
                            "name": "mine.pdf",
                            "url": "https://moodle.example.com/pluginfile.php/1/assignsubmission_file/mine.pdf",
                        },
                    ],
                },
            ],
        }
    ],
    "mod_assign_get_assignments": {
        "courses": [
            {
                "assignments": [
                    {
                        "id": 55,
                        "cmid": 11,
                        "course": 831,
                        "name": "1st Coursework",
                        "duedate": 1,
                    }
                ]
            }
        ]
    },
    "mod_forum_get_forums_by_courses": [
        {"id": 44, "course": 831, "name": "News", "intro": "", "type": "news"}
    ],
    "mod_forum_get_forum_discussions": {
        "discussions": [{"id": 1, "discussion": 99, "subject": "Hello"}]
    },
    "mod_forum_get_discussion_posts": {
        "posts": [{"id": 2, "subject": "Hello", "message": "Hi", "author": {"fullname": "Mehmet"}}]
    },
    "mod_quiz_get_quizzes_by_courses": {"quizzes": []},
    "gradereport_user_get_grade_items": {"usergrades": []},
    "core_enrol_get_enrolled_users": [{"id": 7, "username": "mf", "fullname": "Mehmet"}],
    "core_group_get_course_groups": [],
    "core_group_get_course_groupings": [],
    "core_calendar_get_action_events_by_course": {"events": []},
    "core_calendar_get_action_events_by_timesort": {
        "events": [{"id": 9, "name": "Due", "courseid": 831, "timestart": 1}]
    },
    "core_completion_get_activities_completion_status": {"statuses": []},
    "core_notes_get_course_notes": {"coursenotes": []},
    "mod_choice_get_choices_by_courses": {"choices": []},
    "mod_feedback_get_feedbacks_by_courses": {"feedbacks": []},
    "core_badges_get_user_badges": {"badges": []},
    "core_course_get_categories": [],
    "core_cohort_get_cohorts": [],
    "core_course_get_enrolled_courses_by_timeline_classification": {
        "courses": [{"id": 831, "shortname": "COMP3204", "fullname": "Vision"}]
    },
    "core_course_get_course_module": {
        "cm": {"id": 13, "name": "Page", "modname": "page", "course": 831}
    },
    "core_files_get_files": {
        "files": [
            {
                "filename": "notes.txt",
                "fileurl": "https://moodle.example.com/pluginfile.php/7/notes.txt",
            }
        ]
    },
    "core_course_search_courses": {
        "courses": [{"id": 831, "shortname": "COMP3204", "fullname": "Vision"}]
    },
    "core_message_get_messages": {"messages": []},
    "core_message_get_conversations": {"conversations": []},
    "core_message_get_unread_conversations_count": 0,
}


class FakeClient:
    base_url = "https://moodle.example.com"
    token = ""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def call(self, wsfunction: str, **params: Any) -> Any:
        self.calls.append(wsfunction)
        if wsfunction in RESPONSES:
            return RESPONSES[wsfunction]
        raise AssertionError(wsfunction)


def test_course_by_shortname_and_lazy_contents() -> None:
    client = FakeClient()
    api = Moodle(client)  # ty: ignore[invalid-argument-type]
    course = api.course("COMP3204")
    assert course.id == 831
    assert "core_course_get_contents" not in client.calls
    assert course.sections[0].name == "Schedule"
    assert course.sections[0].table[0]["Topic"] == "Intro"
    assert course.moodle_files[0].name == "COMP3204-CW1.pdf"
    assert all("/assignsubmission_" not in item.url for item in course.moodle_files)
    assert course.assignments[0].id == 55
    assert api.me.username == "mf"
    assert api.site.name == "ECS"
    assert api.timeline("inprogress")[0].short_name == "COMP3204"
    assert api.module(13)["name"] == "Page"
    assert api.files[0].name == "notes.txt"


def test_unknown_shortname_raises() -> None:
    api = Moodle(FakeClient())  # ty: ignore[invalid-argument-type]
    try:
        api.course("NOPE")
    except MoodleAPIError as exc:
        assert "NOPE" in str(exc)
    else:
        raise AssertionError("expected MoodleAPIError")


def test_dump_writes_utf8_json(tmp_path: Path) -> None:
    dest = tmp_path / "COMP3204"
    client = FakeClient()
    api = Moodle(client)  # ty: ignore[invalid-argument-type]
    path = api.course(831).dump(dest, files=False)
    payload = (path / "course.json").read_text(encoding="utf-8")
    assert "COMP3204-CW1.pdf" in payload
    assert "Schedule" in payload
    assert not (path / "files").exists() or not any((path / "files").iterdir())
    assert "mod_forum_get_forum_discussions" not in client.calls
    assert "mod_forum_get_discussion_posts" not in client.calls
    markdown = (path / "course.md").read_text(encoding="utf-8")
    assert "# Vision" in markdown
    assert "| Week | Topic |" in markdown
    assert "[Lecture 1 (Slides)](https://sharepoint.example/slides)" in markdown
    assert "Read the handbook." in markdown
    assert (path / "pages" / "00-Schedule.md").is_file()


def test_dump_pages_html_and_none(tmp_path: Path) -> None:
    api = Moodle(FakeClient())  # ty: ignore[invalid-argument-type]
    html_path = api.course(831).dump(tmp_path / "html", files=False, pages="html")
    html = (html_path / "course.html").read_text(encoding="utf-8")
    assert "<table>" in html
    assert "sharepoint.example/slides" in html
    none_path = api.course(831).dump(tmp_path / "none", files=False, pages="none")
    assert not (none_path / "course.md").exists()
    assert not (none_path / "pages").exists()


def test_file_save_name_uses_url_basename() -> None:
    from moodle_cli.api.export import file_save_name

    assert (
        file_save_name(
            "secret psychological experiment",
            "https://moodle.example.com/pluginfile.php/1/mod_resource/content/1/kramer-et-al-2014.pdf",
        )
        == "kramer-et-al-2014.pdf"
    )


def test_dump_all_writes_site_json(tmp_path: Path) -> None:
    dest = tmp_path / "all"
    api = Moodle(FakeClient())  # ty: ignore[invalid-argument-type]
    path = api.dump(dest, files=False)
    site = (path / "site.json").read_text(encoding="utf-8")
    assert "COMP3204" in site
    assert (path / "COMP3204" / "course.json").is_file()
