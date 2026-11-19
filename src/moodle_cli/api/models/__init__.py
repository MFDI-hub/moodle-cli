"""Dataclasses for Moodle objects. Nested data is loaded on first access."""

from moodle_cli.api.models.activities import (
    Activity,
    Assignment,
    Discussion,
    Forum,
    Quiz,
    Section,
)
from moodle_cli.api.models.base import Remote, safe_name
from moodle_cli.api.models.common import (
    Badge,
    Category,
    Choice,
    Cohort,
    Completion,
    Conversation,
    Event,
    Feedback,
    FileRef,
    Grade,
    Group,
    Message,
    Note,
    Site,
    User,
)
from moodle_cli.api.models.course import Course

__all__ = [
    "Activity",
    "Assignment",
    "Badge",
    "Category",
    "Choice",
    "Cohort",
    "Completion",
    "Conversation",
    "Course",
    "Discussion",
    "Event",
    "Feedback",
    "FileRef",
    "Forum",
    "Grade",
    "Group",
    "Message",
    "Note",
    "Quiz",
    "Remote",
    "Section",
    "Site",
    "User",
    "safe_name",
]
