"""Comment commands."""

from __future__ import annotations

import click

from moodle_cli.cli.main import MoodleContext, handle_errors, pass_context
from moodle_cli.output import console, render_json, render_table
from moodle_cli.services.comment import CommentService


@click.group()
def comment() -> None:
    """Comments on Moodle items."""


@comment.command("list")
@click.option("--contextlevel", required=True)
@click.option("--instanceid", required=True, type=int)
@click.option("--component", required=True)
@click.option("--itemid", required=True, type=int)
@click.option("--area", default="")
@pass_context
@handle_errors
def list_comments(
    ctx: MoodleContext, contextlevel: str, instanceid: int, component: str, itemid: int, area: str
) -> None:
    """List comments on an item."""
    rows = CommentService(ctx.get_client()).list_comments(
        contextlevel, instanceid, component, itemid, area
    )
    if ctx.json_output:
        render_json(rows)
    else:
        table = [
            {"ID": c.get("id"), "User": c.get("userid"), "Content": c.get("content", "")}
            for c in rows
        ]
        render_table(table, title=f"Comments ({len(table)})")


@comment.command()
@click.option("--contextlevel", required=True)
@click.option("--instanceid", required=True, type=int)
@click.option("--component", required=True)
@click.option("--itemid", required=True, type=int)
@click.option("--content", required=True)
@click.option("--area", default="")
@pass_context
@handle_errors
def add(
    ctx: MoodleContext,
    contextlevel: str,
    instanceid: int,
    component: str,
    itemid: int,
    content: str,
    area: str,
) -> None:
    """Add a comment."""
    result = CommentService(ctx.get_client()).add(
        contextlevel, instanceid, component, itemid, content, area
    )
    if ctx.json_output:
        render_json(result)
    else:
        console.print("[green]Added comment.[/green]")
