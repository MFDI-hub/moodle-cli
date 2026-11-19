"""Calendar commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, fmt_ts, render_json, render_table
from moodle_cli.services.calendar import CalendarService


@click.group()
def calendar() -> None:
    """Calendar management."""


@calendar.command()
@click.option("--limit", type=int, default=20, help="Max events to show.")
@pass_context
@handle_errors
def upcoming(ctx: MoodleContext, limit: int) -> None:
    """Upcoming deadlines + events across your courses, soonest first."""
    evts = ctx.get_moodle().upcoming(limit)
    if ctx.json_output:
        render_json([e.to_dict() for e in evts])
    else:
        rows = [
            {"When": fmt_ts(e.time_start), "Course": e.course_id or "-", "Event": e.name}
            for e in evts
        ]
        render_table(rows, title=f"Upcoming ({len(rows)})")


@calendar.command()
@click.argument("course_id", type=int)
@pass_context
@handle_errors
def course(ctx: MoodleContext, course_id: int) -> None:
    """Upcoming deadlines + events for ONE course."""
    evts = ctx.get_moodle().course(course_id).calendar
    if ctx.json_output:
        render_json([e.to_dict() for e in evts])
    else:
        rows = [{"When": fmt_ts(e.time_start), "Event": e.name, "Type": e.event_type} for e in evts]
        render_table(rows, title=f"Course events ({len(rows)})")


@calendar.command()
@click.option("--course-id", type=int, multiple=True, help="Filter by course ID(s)")
@pass_context
@handle_errors
def events(ctx: MoodleContext, course_id: tuple[int, ...]) -> None:
    """List calendar events."""
    svc = CalendarService(ctx.get_client())
    ids = list(course_id) if course_id else None
    evts = svc.get_events(ids)
    if ctx.json_output:
        render_json([e.model_dump() for e in evts])
    else:
        rows = [
            {"ID": e.id, "Name": e.name, "Type": e.event_type, "Start": e.time_start} for e in evts
        ]
        render_table(rows, title=f"Events ({len(rows)})")


@calendar.command()
@click.option("--name", required=True, help="Event name")
@click.option(
    "--timestart", "time_start", required=True, type=int, help="Start time (unix timestamp)"
)
@click.option("--duration", default=0, type=int, help="Duration in seconds")
@click.option("--description", default="", help="Event description")
@click.option("--course-id", default=0, type=int, help="Course ID (for course events)")
@click.option("--type", "event_type", default="user", help="Event type (user, course, site)")
@pass_context
@handle_errors
def create(
    ctx: MoodleContext,
    name: str,
    time_start: int,
    duration: int,
    description: str,
    course_id: int,
    event_type: str,
) -> None:
    """Create a calendar event."""
    svc = CalendarService(ctx.get_client())
    evt = svc.create_event(
        name=name,
        event_type=event_type,
        time_start=time_start,
        time_duration=duration,
        description=description,
        course_id=course_id,
    )
    if ctx.json_output:
        render_json(evt.model_dump())
    else:
        console.print(f"[green]Created event '{evt.name}' (ID: {evt.id})[/green]")


@calendar.command()
@click.argument("event_id", type=int)
@click.option("--name", default=None)
@click.option("--timestart", "time_start", default=None, type=int)
@click.option("--description", default=None)
@pass_context
@handle_errors
def update(
    ctx: MoodleContext,
    event_id: int,
    name: str | None,
    time_start: int | None,
    description: str | None,
) -> None:
    """Update a calendar event."""
    kwargs: dict[str, object] = {}
    if name is not None:
        kwargs["name"] = name
    if time_start is not None:
        kwargs["timestart"] = time_start
    if description is not None:
        kwargs["description"] = description
    result = CalendarService(ctx.get_client()).update_event(event_id, **kwargs)
    if ctx.json_output:
        render_json(result)
    else:
        console.print(f"[green]Updated event {event_id}.[/green]")


@calendar.command()
@click.argument("event_ids", type=int, nargs=-1, required=True)
@pass_context
@handle_errors
def delete(ctx: MoodleContext, event_ids: tuple[int, ...]) -> None:
    """Delete calendar events."""
    CalendarService(ctx.get_client()).delete_events(list(event_ids))
    console.print(f"[green]Deleted {len(event_ids)} event(s).[/green]")
