"""Assignment commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.assign import AssignService
from moodle_cli.services.file import FileService


@click.group()
def assign() -> None:
    """Assignment management."""


@assign.command()
@click.argument("assignment_ids", type=int, nargs=-1, required=True)
@pass_context
@handle_errors
def grades(ctx: MoodleContext, assignment_ids: tuple[int, ...]) -> None:
    """Show grades already given on assignment(s)."""
    svc = AssignService(ctx.get_client())
    rows_data = svc.get_grades(list(assignment_ids))
    if ctx.json_output:
        render_json(rows_data)
    else:
        rows = [
            {"Assignment": g.get("assignment"), "User": g.get("userid"), "Grade": g.get("grade")}
            for g in rows_data
        ]
        render_table(rows, title=f"Grades ({len(rows)})")


@assign.command()
@click.argument("assign_id", type=int)
@click.option("--user-id", type=int, default=None, help="User ID (defaults to current user)")
@pass_context
@handle_errors
def status(ctx: MoodleContext, assign_id: int, user_id: int | None) -> None:
    """Submission + grading status for one assignment / user."""
    svc = AssignService(ctx.get_client())
    data = svc.get_submission_status(assign_id, user_id)
    if ctx.json_output:
        render_json(data)
    else:
        last = data.get("lastattempt", {})
        sub = last.get("submission", {})
        grade = (data.get("feedback") or {}).get("grade") or {}
        console.print(f"Submission status: {sub.get('status', '-')}")
        console.print(f"Grading status:    {sub.get('gradingstatus', '-')}")
        console.print(f"Grade:             {grade.get('grade', '-')}")


@assign.command("list")
@click.option("--course-id", type=int, multiple=True, help="Filter by course ID(s)")
@pass_context
@handle_errors
def list_assignments(ctx: MoodleContext, course_id: tuple[int, ...]) -> None:
    """List assignments."""
    api = ctx.get_moodle()
    ids = list(course_id) if course_id else [course.id for course in api.courses]
    assignments = [item for cid in ids for item in api.course(cid).assignments]
    if ctx.json_output:
        render_json([a.to_dict() for a in assignments])
    else:
        rows = [
            {"ID": a.id, "Course": a.course_id, "Name": a.name, "Due": a.due_date}
            for a in assignments
        ]
        render_table(rows, title=f"Assignments ({len(rows)})")


@assign.command()
@click.argument("assignment_ids", type=int, nargs=-1, required=True)
@pass_context
@handle_errors
def submissions(ctx: MoodleContext, assignment_ids: tuple[int, ...]) -> None:
    """Get submissions for assignment(s)."""
    svc = AssignService(ctx.get_client())
    subs = svc.get_submissions(list(assignment_ids))
    if ctx.json_output:
        render_json([s.model_dump() for s in subs])
    else:
        rows = [
            {"ID": s.id, "User": s.user_id, "Status": s.status, "Grading": s.grading_status}
            for s in subs
        ]
        render_table(rows, title=f"Submissions ({len(rows)})")


@assign.command()
@click.option("--assignment-id", required=True, type=int)
@click.option("--user-id", required=True, type=int)
@click.option("--grade", "grade_value", required=True, type=float)
@click.option("--feedback", default="", help="Feedback comment")
@click.option(
    "--workflow-state",
    default="",
    help=(
        "Marking-workflow state (e.g. 'released'). Leave empty unless the "
        "assignment has marking workflow enabled — a non-empty value on a "
        "non-workflow assignment is rejected by Moodle."
    ),
)
@click.option(
    "--criterion",
    "criteria",
    multiple=True,
    help="Rubric criterion as id=levelid (repeatable).",
)
@pass_context
@handle_errors
def grade(
    ctx: MoodleContext,
    assignment_id: int,
    user_id: int,
    grade_value: float,
    feedback: str,
    workflow_state: str,
    criteria: tuple[str, ...],
) -> None:
    """Grade a submission."""
    svc = AssignService(ctx.get_client())
    advanced = None
    if criteria:
        items = {}
        for pair in criteria:
            cid, level = pair.split("=", 1)
            items[cid] = {"levelid": int(level)}
        advanced = {"criteria": items}
    svc.grade_submission(
        assignment_id, user_id, grade_value, feedback, workflow_state, advanced_grading=advanced
    )
    console.print(
        f"[green]Graded user {user_id} on assignment {assignment_id}: {grade_value}[/green]"
    )


@assign.command()
@click.option("--assignment-id", required=True, type=int)
@click.option("--onlinetext", default="")
@click.option("--file", "files", multiple=True, type=click.Path(exists=True, dir_okay=False))
@pass_context
@handle_errors
def save(ctx: MoodleContext, assignment_id: int, onlinetext: str, files: tuple[str, ...]) -> None:
    """Save a draft submission (text and/or files)."""
    plugin_data: dict[str, object] = {}
    if onlinetext:
        plugin_data["onlinetext_editor"] = {"text": onlinetext, "format": 1, "itemid": 0}
    if files:
        uploaded = FileService(ctx.get_client()).upload(files[0])
        itemid = 0
        if isinstance(uploaded, list) and uploaded:
            itemid = int(uploaded[0].get("itemid") or 0)
        plugin_data["files_filemanager"] = itemid
    result = AssignService(ctx.get_client()).save_submission(assignment_id, plugin_data)
    if ctx.json_output:
        render_json(result)
    else:
        console.print(f"[green]Saved submission on assignment {assignment_id}.[/green]")


@assign.command()
@click.option("--assignment-id", required=True, type=int)
@pass_context
@handle_errors
def submit(ctx: MoodleContext, assignment_id: int) -> None:
    """Submit the saved assignment for grading."""
    result = AssignService(ctx.get_client()).submit_for_grading(assignment_id)
    if ctx.json_output:
        render_json(result)
    else:
        console.print(f"[green]Submitted assignment {assignment_id}.[/green]")


@assign.command("rubric")
@click.argument("cmid", type=int)
@pass_context
@handle_errors
def rubric(ctx: MoodleContext, cmid: int) -> None:
    """Show rubric or marking-guide definitions for an assignment."""
    data = AssignService(ctx.get_client()).grading_definitions(cmid)
    render_json(data) if ctx.json_output else console.print(data)
