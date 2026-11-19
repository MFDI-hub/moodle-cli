"""Calendar service."""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import Field

from moodle_cli.services.base import BaseService, MoodleModel


class CalendarEvent(MoodleModel):
    id: int
    name: str = ""
    description: str = ""
    event_type: Annotated[str, Field(validation_alias="eventtype")] = ""
    course_id: Annotated[int, Field(validation_alias="courseid")] = 0
    time_start: Annotated[int, Field(validation_alias="timestart")] = 0
    time_duration: Annotated[int, Field(validation_alias="timeduration")] = 0


class CalendarService(BaseService):
    def get_events(self, course_ids: list[int] | None = None) -> list[CalendarEvent]:
        events: dict[str, Any] = {}
        options: dict[str, Any] = {"userevents": 1, "siteevents": 1}
        if course_ids:
            events["courseids"] = course_ids
        data = self.call(
            "core_calendar_get_calendar_events",
            events=events,
            options=options,
        )
        return [CalendarEvent.model_validate(e) for e in data.get("events", [])]

    def get_upcoming(self, limit: int = 20) -> list[CalendarEvent]:
        """Upcoming action events sorted by time (core_calendar_get_action_events_by_timesort).

        The "what's coming up" view — assignment due-dates, quiz closes and scheduled
        events across all the user's courses, soonest first.
        """
        data = self.call("core_calendar_get_action_events_by_timesort", limitnum=limit)
        return [CalendarEvent.model_validate(e) for e in data.get("events", [])]

    def get_course_events(self, course_id: int) -> list[CalendarEvent]:
        """Action events (deadlines etc.) for a single course
        (core_calendar_get_action_events_by_course)."""
        data = self.call("core_calendar_get_action_events_by_course", courseid=course_id)
        return [CalendarEvent.model_validate(e) for e in data.get("events", [])]

    def create_event(
        self,
        name: str,
        event_type: str = "user",
        time_start: int = 0,
        time_duration: int = 0,
        description: str = "",
        course_id: int = 0,
    ) -> CalendarEvent:
        event_data: dict[str, Any] = {
            "name": name,
            "eventtype": event_type,
            "timestart": time_start,
            "timeduration": time_duration,
            "description": description,
        }
        if course_id:
            event_data["courseid"] = course_id
        data = self.call("core_calendar_create_calendar_events", events=[event_data])
        return CalendarEvent.model_validate(data["events"][0])

    def update_event(self, event_id: int, **kwargs: Any) -> Any:
        formdata = {"id": event_id, **kwargs}
        return self.call("core_calendar_submit_create_update_form", formdata=formdata)

    def delete_events(self, event_ids: list[int], repeat: int = 0) -> None:
        self.call(
            "core_calendar_delete_calendar_events",
            events=[{"eventid": eid, "repeat": repeat} for eid in event_ids],
        )
