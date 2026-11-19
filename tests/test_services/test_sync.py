"""Incremental sync store and collectors."""

from __future__ import annotations

from pathlib import Path

from moodle_cli.client.http import MoodleHTTPClient
from moodle_cli.services.assign import AssignService
from moodle_cli.services.course import CourseService
from moodle_cli.services.sync import SyncStore, unique_path
from tests.conftest import BASE_URL, TOKEN
from tests.http_mock import Response, Router


def test_sync_store_skips_unchanged_and_keeps_removed(tmp_path: Path) -> None:
    store = SyncStore(tmp_path / "sync.db")
    store.upsert("https://moodle.example.com/f.pdf", 1, str(tmp_path / "f.pdf"), 10, 100, "abc")
    row = store.get("https://moodle.example.com/f.pdf")
    assert row is not None
    assert row["size"] == 10
    gone = store.mark_removed(set(), 1)
    assert str(tmp_path / "f.pdf") in gone
    row = store.get("https://moodle.example.com/f.pdf")
    assert row is not None
    assert row["status"] == "removed"
    store.close()


def test_unique_path_avoids_collisions(tmp_path: Path) -> None:
    used: set[str] = set()
    first = unique_path(tmp_path, "a.pdf", used)
    second = unique_path(tmp_path, "a.pdf", used)
    assert first != second


def test_submission_files(mock_http: Router) -> None:
    mock_http.post(f"{BASE_URL}/webservice/rest/server.php").mock(
        return_value=Response(
            200,
            json={
                "assignments": [
                    {
                        "assignmentid": 9,
                        "submissions": [
                            {
                                "plugins": [
                                    {
                                        "fileareas": [
                                            {
                                                "files": [
                                                    {
                                                        "fileurl": "https://moodle.example.com/pluginfile.php/1/assignsubmission_file/x",
                                                        "filename": "work.pdf",
                                                        "filesize": 4,
                                                        "timemodified": 1,
                                                    }
                                                ]
                                            }
                                        ]
                                    }
                                ]
                            }
                        ],
                    }
                ]
            },
        )
    )
    files = AssignService(MoodleHTTPClient(BASE_URL, TOKEN)).submission_files(9)
    assert files[0]["name"] == "work.pdf"
    assert "assignsubmission_file" in files[0]["url"]


def test_ensure_course_creates_when_missing() -> None:
    client = MoodleHTTPClient(BASE_URL, TOKEN)
    svc = CourseService(client)

    def fake_call(wsfunction: str, **params: object) -> object:
        if wsfunction == "core_course_get_courses":
            return []
        return [{"id": 8, "shortname": "NEW", "fullname": "New", "categoryid": 1}]

    svc.call = fake_call
    course, created = svc.ensure_course("NEW", "New", 1)
    assert created is True
    assert course.short_name == "NEW"
