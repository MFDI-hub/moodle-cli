"""Tests for course service."""

from __future__ import annotations

from moodle_cli.client.http import MoodleHTTPClient
from moodle_cli.services.course import CourseService
from tests.conftest import BASE_URL, TOKEN, load_fixture
from tests.http_mock import Response, Router


class TestCourseService:
    def test_list_courses(self, mock_http: Router) -> None:
        fixture = load_fixture("courses")
        mock_http.post(f"{BASE_URL}/webservice/rest/server.php").mock(
            return_value=Response(200, json=fixture)
        )
        client = MoodleHTTPClient(base_url=BASE_URL, token=TOKEN)
        svc = CourseService(client)
        courses = svc.list_courses()

        assert len(courses) == 2
        assert courses[1].short_name == "MATH101"
        assert courses[1].full_name == "Introduction to Mathematics"

    def test_get_course(self, mock_http: Router) -> None:
        mock_http.post(f"{BASE_URL}/webservice/rest/server.php").mock(
            return_value=Response(
                200,
                json=[
                    {
                        "id": 2,
                        "shortname": "MATH101",
                        "fullname": "Introduction to Mathematics",
                        "categoryid": 1,
                    }
                ],
            )
        )
        client = MoodleHTTPClient(base_url=BASE_URL, token=TOKEN)
        svc = CourseService(client)
        course = svc.get_course(2)

        assert course.id == 2
        assert course.short_name == "MATH101"

    def test_search_courses(self, mock_http: Router) -> None:
        mock_http.post(f"{BASE_URL}/webservice/rest/server.php").mock(
            return_value=Response(
                200,
                json={
                    "courses": [
                        {
                            "id": 2,
                            "shortname": "MATH101",
                            "fullname": "Introduction to Mathematics",
                            "categoryid": 1,
                        }
                    ],
                    "total": 1,
                },
            )
        )
        client = MoodleHTTPClient(base_url=BASE_URL, token=TOKEN)
        svc = CourseService(client)
        results = svc.search_courses("math")

        assert len(results) == 1
        assert results[0].short_name == "MATH101"
