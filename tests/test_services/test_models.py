"""Guard Moodle wire aliases on service models."""

from __future__ import annotations

from moodle_cli.services.course import CourseRecord


def test_course_record_accepts_wire_names() -> None:
    record = CourseRecord.model_validate(
        {"id": 1, "shortname": "X", "fullname": "Y", "categoryid": 3}
    )
    assert record.short_name == "X"
    assert record.full_name == "Y"
    assert record.category_id == 3
    dumped = record.model_dump()
    assert dumped["short_name"] == "X"
    assert dumped["full_name"] == "Y"
    assert dumped["category_id"] == 3
    assert "shortname" not in dumped
    assert "fullname" not in dumped
    assert "categoryid" not in dumped
