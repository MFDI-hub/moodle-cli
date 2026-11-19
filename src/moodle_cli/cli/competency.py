"""Competency commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.competency import CompetencyService


@click.group()
def competency() -> None:
    """Competencies."""


@competency.command("course")
@click.argument("course_id", type=int)
@pass_context
@handle_errors
def course_competencies(ctx: MoodleContext, course_id: int) -> None:
    """List competencies linked to a course."""
    data = CompetencyService(ctx.get_client()).course_competencies(course_id)
    if ctx.json_output:
        render_json(data)
    else:
        rows = data if isinstance(data, list) else [data]
        table = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            comp = row.get("competency") or row
            table.append(
                {"ID": comp.get("id"), "Name": comp.get("shortname") or comp.get("idnumber", "")}
            )
        render_table(table, title=f"Competencies ({len(table)})")


@competency.command()
@click.option("--course-id", required=True, type=int)
@click.option("--competency-id", required=True, type=int)
@click.option("--user-id", required=True, type=int)
@click.option("--grade", required=True, type=int)
@click.option("--note", default="")
@pass_context
@handle_errors
def grade(
    ctx: MoodleContext, course_id: int, competency_id: int, user_id: int, grade: int, note: str
) -> None:
    """Grade a competency in a course."""
    result = CompetencyService(ctx.get_client()).grade(
        course_id, competency_id, user_id, grade, note
    )
    if ctx.json_output:
        render_json(result)
    else:
        console.print("[green]Graded competency.[/green]")
