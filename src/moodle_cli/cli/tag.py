"""Tag commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import render_json, render_table
from moodle_cli.services.tag import TagService


@click.group()
def tag() -> None:
    """Tags."""


@tag.command("list")
@click.option("--query", default="")
@pass_context
@handle_errors
def list_tags(ctx: MoodleContext, query: str) -> None:
    """List tags."""
    rows = TagService(ctx.get_client()).list_tags(query)
    if ctx.json_output:
        render_json(rows)
    else:
        table = [{"ID": t.get("id"), "Name": t.get("name") or t.get("rawname", "")} for t in rows]
        render_table(table, title=f"Tags ({len(table)})")
