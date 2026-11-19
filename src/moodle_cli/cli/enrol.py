"""Enrolment commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import ago, fmt_ts, render_json, render_table
from moodle_cli.services.enrol import EnrolService


@click.group()
def enrol() -> None:
    """Enrolment management."""


@enrol.command("my-courses")
@pass_context
@handle_errors
def my_courses(ctx: MoodleContext) -> None:
    """List courses the current user is enrolled in."""
    courses = list(ctx.get_moodle().courses)
    if ctx.json_output:
        render_json([c.to_dict() for c in courses])
    else:
        rows = [
            {
                "ID": c.id,
                "Short Name": c.short_name,
                "Full Name": c.full_name,
                "Last access": ago(c.last_access),
            }
            for c in courses
        ]
        render_table(rows, title=f"My Courses ({len(rows)})")


@enrol.command("list-users")
@click.argument("course_id", type=int)
@click.option(
    "--role", default=None, help="Filter by role shortname (e.g. student, editingteacher)."
)
@pass_context
@handle_errors
def list_users(ctx: MoodleContext, course_id: int, role: str | None) -> None:
    """List enrolled users in a course, with role + last-access (engagement signal)."""
    users = ctx.get_moodle().course(course_id).people
    if role:
        users = [u for u in users if any(r.get("shortname") == role for r in u.roles)]
    if ctx.json_output:
        render_json([u.to_dict() for u in users])
    else:
        rows = [
            {
                "ID": u.id,
                "Full Name": u.full_name,
                "Role": ", ".join(str(r.get("shortname") or "") for r in u.roles) or "-",
                "Email": u.email,
                "Last access": fmt_ts(u.last_course_access or u.last_access),
                "Ago": ago(u.last_course_access or u.last_access),
            }
            for u in users
        ]
        render_table(rows, title=f"Enrolled Users ({len(rows)})")


@enrol.command()
@click.argument("course_id", type=int)
@pass_context
@handle_errors
def methods(ctx: MoodleContext, course_id: int) -> None:
    """List the enrolment methods active in a course."""
    svc = EnrolService(ctx.get_client())
    methods = svc.get_enrolment_methods(course_id)
    if ctx.json_output:
        render_json([m.model_dump() for m in methods])
    else:
        rows = [{"ID": m.id, "Type": m.type, "Name": m.name, "Status": m.status} for m in methods]
        render_table(rows, title=f"Enrolment Methods ({len(rows)})")


@enrol.command()
@click.argument("course_id", type=int)
@click.argument("user_ids", type=int, nargs=-1, required=True)
@click.option("--role-id", default=5, type=int, help="Role id (default 5 = student).")
@pass_context
@handle_errors
def add(ctx: MoodleContext, course_id: int, user_ids: tuple[int, ...], role_id: int) -> None:
    """Manually enrol users on a course."""
    from moodle_cli.output import console

    result = EnrolService(ctx.get_client()).enrol_users(course_id, list(user_ids), role_id)
    if ctx.json_output:
        render_json(result)
    else:
        console.print(f"[green]Enrolled {len(user_ids)} user(s) on course {course_id}.[/green]")


@enrol.command()
@click.argument("course_id", type=int)
@click.argument("user_ids", type=int, nargs=-1, required=True)
@pass_context
@handle_errors
def remove(ctx: MoodleContext, course_id: int, user_ids: tuple[int, ...]) -> None:
    """Manually unenrol users from a course."""
    from moodle_cli.output import console

    result = EnrolService(ctx.get_client()).unenrol_users(course_id, list(user_ids))
    if ctx.json_output:
        render_json(result)
    else:
        console.print(f"[green]Unenrolled {len(user_ids)} user(s) from course {course_id}.[/green]")


@enrol.command("self")
@click.argument("course_id", type=int)
@click.option("--password", default="")
@pass_context
@handle_errors
def self_enrol(ctx: MoodleContext, course_id: int, password: str) -> None:
    """Self-enrol the current user."""
    from moodle_cli.output import console

    result = EnrolService(ctx.get_client()).self_enrol(course_id, password)
    if ctx.json_output:
        render_json(result)
    else:
        console.print(f"[green]Self-enrolled on course {course_id}.[/green]")


@enrol.command("cohort")
@click.argument("course_id", type=int)
@click.argument("cohort_id", type=int)
@pass_context
@handle_errors
def cohort_enrol(ctx: MoodleContext, course_id: int, cohort_id: int) -> None:
    """Add a cohort enrolment instance if the site exposes it."""
    from moodle_cli.output import console

    result = EnrolService(ctx.get_client()).cohort_enrol(course_id, cohort_id)
    if ctx.json_output:
        render_json(result)
    else:
        console.print(f"[green]Linked cohort {cohort_id} to course {course_id}.[/green]")
