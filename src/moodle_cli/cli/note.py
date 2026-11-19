"""Notes commands."""

from __future__ import annotations

import re

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import render_json, render_table, trim


@click.group()
def note() -> None:
    """Teacher notes on users."""


@note.command()
@click.argument("course_id", type=int)
@pass_context
@handle_errors
def course(ctx: MoodleContext, course_id: int) -> None:
    """List notes recorded against users in a course."""
    notes = ctx.get_moodle().course(course_id).notes
    if ctx.json_output:
        render_json([n.to_dict() for n in notes])
    else:
        rows = [
            {
                "ID": n.id,
                "User": n.user_id,
                "Note": trim(
                    re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", n.content)).strip(),
                    ctx.trim_messages,
                ),
            }
            for n in notes
        ]
        render_table(rows, title=f"Course notes ({len(rows)})")
