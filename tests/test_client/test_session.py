"""Tests for browser-session login."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from click.testing import CliRunner

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

from moodle_cli.cli.main import cli
from moodle_cli.client.exceptions import AuthenticationError, MoodleAPIError
from moodle_cli.client.session import (
    MoodleSessionClient,
    activity_document,
    course_record,
    extract_moodle_cfg,
    section_summary,
    sections_from_state,
)
from moodle_cli.client.storage import site_url_from_storage
from tests.http_mock import Response, Router

BASE_URL = "https://moodle.example.com"


def _storage(path: Path, *, domain: str = "moodle.example.com") -> Path:
    path.write_text(
        json.dumps(
            {
                "cookies": [
                    {
                        "name": "MoodleSession",
                        "value": "session-secret",
                        "domain": domain,
                        "path": "/",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def _client(path: Path) -> MoodleSessionClient:
    client = MoodleSessionClient(BASE_URL, path)
    client._ready = True
    client.user_id = 7
    client.sesskey = "sess"
    return client


def test_site_url_from_storage(tmp_path: Path) -> None:
    path = _storage(tmp_path / "state.json")
    assert site_url_from_storage(path) == BASE_URL


def test_site_url_missing_cookie(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"cookies": []}), encoding="utf-8")
    try:
        site_url_from_storage(path)
    except AuthenticationError as exc:
        assert "MoodleSession" in str(exc)
    else:
        raise AssertionError("expected AuthenticationError")


def test_extract_cfg_nested() -> None:
    html = 'M.cfg = {"userId": 7, "sesskey": "abc", "deprecationignorelist": {"a": 1}};'
    assert extract_moodle_cfg(html)["userId"] == 7


def test_course_record_normalizes_progress() -> None:
    record = course_record(
        {"id": 3, "shortname": "COMP", "fullname": "Vision", "visible": True, "progress": False}
    )
    assert record["id"] == 3
    assert record["visible"] == 1
    assert record["progress"] is None
    encoded = course_record(
        {"id": 1, "shortname": "A", "fullname": "Responsibility &#38; Conduct", "visible": 1}
    )
    assert encoded["fullname"] == "Responsibility & Conduct"


def test_sections_from_state() -> None:
    sections = sections_from_state(
        {
            "section": [{"id": 10, "rawtitle": "Week 1", "cmlist": [4]}],
            "cm": [
                {"id": 4, "name": "Slides", "modname": "resource", "url": "https://example/mod"}
            ],
        }
    )
    assert sections[0]["name"] == "Week 1"
    assert sections[0]["modules"][0]["modname"] == "resource"


def test_ajax_call_unwraps_data(mock_http: Router, tmp_path: Path) -> None:
    mock_http.post(f"{BASE_URL}/lib/ajax/service.php").mock(
        return_value=Response(200, json=[{"error": False, "data": {"events": [{"id": 1}]}}])
    )
    client = _client(_storage(tmp_path / "state.json"))
    events = client.call("core_calendar_get_action_events_by_timesort", limitnum=1)["events"]
    assert events[0]["id"] == 1


def test_ajax_call_raises_moodle_error(mock_http: Router, tmp_path: Path) -> None:
    mock_http.post(f"{BASE_URL}/lib/ajax/service.php").mock(
        return_value=Response(
            200,
            json=[
                {
                    "error": True,
                    "exception": {"errorcode": "servicenotavailable", "message": "missing"},
                }
            ],
        )
    )
    client = _client(_storage(tmp_path / "state.json"))
    try:
        client.call("core_comment_get_comments")
    except MoodleAPIError as exc:
        assert exc.error_code == "servicenotavailable"
    else:
        raise AssertionError("expected MoodleAPIError")


def test_enrolled_courses_use_timeline(tmp_path: Path) -> None:
    client = _client(_storage(tmp_path / "state.json"))

    def fake_ajax(name: str, args: dict[str, object]) -> dict[str, object]:
        assert "timeline_classification" in name
        assert args["classification"] == "all"
        return {
            "courses": [{"id": 8, "shortname": "COMP3227", "fullname": "Web", "visible": 1}],
            "nextoffset": 1,
        }

    client._ajax = fake_ajax  # ty: ignore[invalid-assignment]
    courses = client.call("core_enrol_get_users_courses")
    assert courses[0]["fullname"] == "Web"


def test_auth_session_saves_profile(
    mock_http: Router, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _storage(tmp_path / "state.json")
    page = type(
        "Page",
        (),
        {
            "status_code": 200,
            "url": f"{BASE_URL}/my/",
            "text": 'M.cfg = {"userId": 7, "sesskey": "abc"};',
            "raise_for_status": lambda _self: None,
        },
    )()

    def fake_get(self: object, url: str, **kwargs: object) -> object:
        return page

    from curl_cffi import Session

    monkeypatch.setattr(Session, "get", fake_get)
    user_route = mock_http.post(f"{BASE_URL}/lib/ajax/service.php").mock(
        return_value=Response(
            200,
            json=[
                {
                    "error": False,
                    "data": [
                        {
                            "id": 7,
                            "username": "mf",
                            "fullname": "Mehmet Icen",
                            "firstname": "Mehmet",
                            "lastname": "Icen",
                            "lang": "en",
                        }
                    ],
                }
            ],
        )
    )
    mock_http.post(f"{BASE_URL}/lib/ajax/service-nologin.php").mock(
        return_value=Response(
            200,
            json=[{"error": False, "data": {"sitename": "ECS", "wwwroot": BASE_URL, "lang": "en"}}],
        )
    )
    result = CliRunner().invoke(
        cli,
        ["auth", "session", "--storage-state", str(path), "--name", "soton"],
    )
    assert result.exit_code == 0, result.output
    assert "Logged in as mf" in result.output
    posted = user_route.calls.last.request.content.decode()
    assert '"7"' in posted
    assert '"0"' not in posted
    status = CliRunner().invoke(cli, ["auth", "status", "--name", "soton"])
    assert status.exit_code == 0
    assert "browser session" in status.output


def test_section_summary_keeps_text_and_file_links() -> None:
    summary, links, table = section_summary(
        """
        <div class="summarytext">
          <div class="no-overflow">
            <p>Read the notes.</p>
            <a href="https://moodle.example.com/course/section.php?id=2">About</a>
            <a href="https://files.example/slides.pdf">PDF</a>
          </div>
        </div>
        """,
        BASE_URL,
    )
    assert "Read the notes." in summary
    assert [link["url"] for link in links] == ["https://files.example/slides.pdf"]
    assert table == []


def test_activity_document_reads_page_folder_and_url() -> None:
    page = activity_document(
        '<div id="region-main"><div class="generalbox"><div class="no-overflow">'
        "<p>Teaching team</p></div></div></div>"
    )
    assert page["text"] == "Teaching team"
    folder = activity_document(
        '<div id="region-main">'
        '<a href="/pluginfile.php/1/theme_boost_union/favicon/logo.png">logo</a>'
        '<a href="/pluginfile.php/9/mod_folder/content/0/intro.pptx?forcedownload=1">Intro</a>'
        "</div>",
        BASE_URL,
    )
    assert folder["files"] == [
        {
            "name": "Intro",
            "url": f"{BASE_URL}/pluginfile.php/9/mod_folder/content/0/intro.pptx?forcedownload=1",
        }
    ]
    external = activity_document(
        '<div id="region-main"><div class="urlworkaround">'
        'Click on <a href="https://handin.example/work">Coursework</a> to open the resource.'
        "</div></div>"
    )
    assert external["target"] == "https://handin.example/work"
    assert "text" not in external


def test_contents_include_summary_text_and_file_url(tmp_path: Path) -> None:
    client = _client(_storage(tmp_path / "state.json"))
    state = {
        "section": [{"id": 10, "rawtitle": "Week", "cmlist": [4, 5]}],
        "cm": [
            {
                "id": 4,
                "name": "Notes",
                "modname": "Page",
                "module": "page",
                "url": f"{BASE_URL}/mod/page/view.php?id=4",
            },
            {
                "id": 5,
                "name": "Slides",
                "modname": "File",
                "module": "resource",
                "url": f"{BASE_URL}/mod/resource/view.php?id=5",
            },
        ],
    }

    def fake_ajax(name: str, args: dict[str, object]) -> Any:
        assert name == "core_courseformat_get_state"
        assert args["courseid"] == 1
        return state

    class Page:
        def __init__(
            self, status: int, text: str = "", headers: dict[str, str] | None = None
        ) -> None:
            self.status_code = status
            self.text = text
            self.headers = headers or {}
            self.url = ""

    def fake_open(url: str, *, follow: bool = True) -> Page | None:
        if "section.php" in url:
            return Page(
                200,
                """
                <div class="summarytext"><div class="no-overflow">
                  <p>Week table</p>
                  <a href="https://files.example/a.pdf">PDF</a>
                </div></div>
                <div id="module-4"><div class="activity-altcontent"><p>Label</p></div></div>
                """,
                {"content-type": "text/html"},
            )
        if "/mod/page/" in url:
            return Page(
                200,
                '<div id="region-main"><div class="generalbox"><p>Page body</p></div></div>',
                {"content-type": "text/html"},
            )
        if "/mod/resource/" in url:
            assert follow is False
            return Page(302, headers={"location": f"{BASE_URL}/pluginfile.php/1/slides.pdf"})
        return None

    client._ajax = fake_ajax  # ty: ignore[invalid-assignment]
    client._open = fake_open
    sections = client.call("core_course_get_contents", courseid=1)
    section = sections[0]
    assert "Week table" in section["summary"]
    notes = section["modules"][0]
    assert notes["text"] == "Page body"
    slides = section["modules"][1]
    assert slides["files"][0]["name"] == "slides.pdf"
    assert section["modules"][2]["url"] == "https://files.example/a.pdf"


def test_timeline_unescapes_names(tmp_path: Path) -> None:
    client = _client(_storage(tmp_path / "state.json"))

    def fake_ajax(name: str, args: dict[str, object]) -> dict[str, object]:
        assert "timeline_classification" in name
        return {
            "courses": [
                {
                    "id": 1,
                    "shortname": "A",
                    "fullname": "Responsibility &#38; Conduct",
                    "visible": 1,
                }
            ],
            "nextoffset": 1,
        }

    client._ajax = fake_ajax  # ty: ignore[invalid-assignment]
    page = client.call(
        "core_course_get_enrolled_courses_by_timeline_classification",
        classification="all",
    )
    assert page["courses"][0]["fullname"] == "Responsibility & Conduct"


def test_calendar_fills_course_id_and_unescapes(mock_http: Router, tmp_path: Path) -> None:
    mock_http.post(f"{BASE_URL}/lib/ajax/service.php").mock(
        return_value=Response(
            200,
            json=[
                {
                    "error": False,
                    "data": {
                        "events": [
                            {
                                "id": 9,
                                "name": "Exam Q&#38;A Forum",
                                "courseid": 0,
                                "course": {"id": 831, "fullname": "Vision"},
                                "timestart": 10,
                            }
                        ]
                    },
                }
            ],
        )
    )
    client = _client(_storage(tmp_path / "state.json"))
    event = client.call("core_calendar_get_action_events_by_timesort", limitnum=1)["events"][0]
    assert event["name"] == "Exam Q&A Forum"
    assert event["courseid"] == 831


def test_site_info_lists_session_functions(tmp_path: Path) -> None:
    client = _client(_storage(tmp_path / "state.json"))

    def fake_ajax(name: str, args: dict[str, object]) -> object:
        if "users_by_field" in name:
            return [
                {
                    "id": 7,
                    "username": "mf",
                    "fullname": "Mehmet",
                    "firstname": "Mehmet",
                    "lastname": "Icen",
                    "lang": "en",
                }
            ]
        raise MoodleAPIError("missing", error_code="servicenotavailable")

    client._ajax = fake_ajax  # ty: ignore[invalid-assignment]
    client._public_config = lambda: {"sitename": "ECS", "wwwroot": BASE_URL, "lang": "en"}
    names = {item["name"] for item in client.call("core_webservice_get_site_info")["functions"]}
    assert "mod_assign_get_assignments" in names
    assert "core_course_get_contents" in names


def _unavailable(name: str, args: dict[str, object]) -> object:
    if "timeline_classification" in name:
        return {
            "courses": [{"id": 831, "shortname": "C", "fullname": "Vision", "visible": 1}],
            "nextoffset": 1,
        }
    if name == "core_courseformat_get_state":
        return {
            "cm": [
                {
                    "id": 10,
                    "name": "CW1",
                    "module": "assign",
                    "modname": "Assignment",
                    "url": f"{BASE_URL}/mod/assign/view.php?id=10",
                },
                {
                    "id": 11,
                    "name": "News",
                    "module": "forum",
                    "modname": "Forum",
                    "url": f"{BASE_URL}/mod/forum/view.php?id=11",
                },
                {
                    "id": 12,
                    "name": "Quiz 1",
                    "module": "quiz",
                    "modname": "Quiz",
                    "url": f"{BASE_URL}/mod/quiz/view.php?id=12",
                },
                {
                    "id": 13,
                    "name": "Notes",
                    "module": "page",
                    "modname": "Page",
                    "url": f"{BASE_URL}/mod/page/view.php?id=13",
                },
            ]
        }
    raise MoodleAPIError("missing", error_code="servicenotavailable")


def test_grade_and_assign_forum_quiz_fallbacks(tmp_path: Path) -> None:
    client = _client(_storage(tmp_path / "state.json"))
    client._ajax = _unavailable  # ty: ignore[invalid-assignment]

    def fake_html(url: str) -> str:
        if "grade/report" in url:
            return """
            <table>
              <tr><th class="column-itemname">Grade item</th>
                  <td class="column-grade">Grade</td></tr>
              <tr><th class="column-itemname">Coursework</th>
                  <td class="column-grade">85.00</td>
                  <td class="column-range">0-100</td></tr>
            </table>
            """
        if "/mod/assign/" in url:
            return """
            <h1>CW1</h1>
            <input type="hidden" name="assignid" value="55">
            <time datetime="2026-11-17T12:00:00+00:00">due</time>
            Submitted for grading. Grade: 90.00
            """
        if "/mod/forum/view" in url:
            return """
            <h1>News</h1>
            <input type="hidden" name="f" value="44">
            <table><tr><td><a href="/mod/forum/discuss.php?d=99">Welcome</a></td>
            <td><a href="/user/view.php?id=2">Ada</a></td><td>3</td></tr></table>
            """
        if "/mod/forum/discuss" in url:
            return """
            <article class="forumpost" id="p7">
              <h3>Welcome</h3>
              <a href="/user/view.php?id=2">Ada</a>
              <div class="post-message">Hello class</div>
            </article>
            """
        if "/mod/quiz/" in url:
            return """
            <h1>Quiz 1</h1>
            <input type="hidden" name="quizid" value="77">
            Highest grade: 8.5
            <table><tr><td>1</td><td>Finished</td><td>8.50</td>
            <td><a href="/mod/quiz/review.php?attempt=3">Review</a></td></tr></table>
            """
        if "user/index" in url:
            return """
            <table id="participants"><tr>
              <td><a href="/user/view.php?id=7&course=831">Mehmet Icen</a></td>
              <td>mf@example.com</td><td>Student</td>
            </tr></table>
            """
        if "group/index" in url:
            return '<select id="groups"><option value="0">Choose</option><option value="5">Lab A (2)</option></select>'
        if "course/index" in url:
            return '<a href="/course/index.php?categoryid=57">Computer Science</a>'
        if "message/index" in url:
            return '<div data-conversation-id="3">Ada</div><div data-message-id="8">Hi</div>'
        if "badges" in url:
            return '<div class="badge"><h3>Starter</h3></div>'
        if "user/files" in url:
            return '<a href="/pluginfile.php/9/user/private/notes.pdf">notes.pdf</a>'
        return "<h1>Page</h1>"

    client._html = fake_html
    items = client.call("gradereport_user_get_grade_items", courseid=831)["usergrades"][0][
        "gradeitems"
    ]
    assert items[0]["itemname"] == "Coursework"
    assert items[0]["grade"] == "85.00"
    assigns = client.call("mod_assign_get_assignments", courseids=[831])["courses"][0][
        "assignments"
    ]
    assert assigns[0]["id"] == 55
    assert assigns[0]["cmid"] == 10
    status = client.call("mod_assign_get_submission_status", assignid=55)
    assert status["lastattempt"]["submission"]["status"] == "submitted"
    forums = client.call("mod_forum_get_forums_by_courses", courseids=[831])
    assert forums[0]["id"] == 44
    discussions = client.call("mod_forum_get_forum_discussions", forumid=44)["discussions"]
    assert discussions[0]["discussion"] == 99
    posts = client.call("mod_forum_get_discussion_posts", discussionid=99)["posts"]
    assert "Hello class" in posts[0]["message"]
    quizzes = client.call("mod_quiz_get_quizzes_by_courses", courseids=[831])["quizzes"]
    assert quizzes[0]["id"] == 77
    people = client.call("core_enrol_get_enrolled_users", courseid=831)
    assert people[0]["id"] == 7
    groups = client.call("core_group_get_course_groups", courseid=831)
    assert groups[0]["name"] == "Lab A"
    cats = client.call("core_course_get_categories")
    assert cats[0]["id"] == 57
    pages = client.call("mod_page_get_pages_by_courses", courseids=[831])["pages"]
    assert pages[0]["coursemodule"] == 13
    cm = client.call("core_course_get_course_module", cmid=13)["cm"]
    assert cm["name"] == "Notes"
    conversations = client.call("core_message_get_conversations", userid=7)["conversations"]
    assert conversations[0]["id"] == 3
    badges = client.call("core_badges_get_user_badges", userid=7)["badges"]
    assert badges[0]["name"] == "Starter"
    files = client.call("core_files_get_files", contextid=1)["files"]
    assert files[0]["filename"] == "notes.pdf"


def test_file_download_writes_bytes(tmp_path: Path) -> None:
    from moodle_cli.services.file import FileService

    client = _client(_storage(tmp_path / "state.json"))
    dest = tmp_path / "out"
    dest.mkdir()

    class FileResp:
        def __init__(self) -> None:
            self.status_code = 200
            self.content = b"%PDF"
            self.url = f"{BASE_URL}/pluginfile.php/1/mod_resource/content/0/slides.pdf"
            self.headers = {"content-disposition": 'inline; filename="slides.pdf"'}

        def raise_for_status(self) -> None:
            return None

    def fake_get(_url: str, **_kwargs: object) -> FileResp:
        return FileResp()

    client.session.get = fake_get  # ty: ignore[invalid-assignment]
    result = FileService(client).download(f"{BASE_URL}/pluginfile.php/1/x", str(dest))
    assert result["filename"] == "slides.pdf"
    assert (dest / "slides.pdf").read_bytes() == b"%PDF"
